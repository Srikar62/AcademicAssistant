"""
Quiz router — generates structured multiple-choice quizzes from documents.

POST /quiz
  - Retrieves relevant chunks from Qdrant
  - Sends them to the LLM with structured JSON-mode prompting
  - Validates the response against the quiz schema
  - Returns schema-validated quiz questions
"""

import json
import logging

from fastapi import APIRouter, HTTPException, status

from backend.app.models.generation import (
    QuizRequest,
    QuizResponse,
    QuizQuestion,
)
from backend.app.services.embedding_service import embed_query
from backend.app.services.qdrant_service import qdrant_retrieval_service
from backend.app.services.llm_client import llm_client
from backend.app.utils.prompts import build_quiz_messages

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Generation"])


def _validate_quiz_json(data: dict, expected_count: int) -> list:
    """
    Validate and parse the LLM's quiz JSON response.

    Handles common LLM quirks and enforces the schema.
    Returns a list of validated QuizQuestion objects.
    """
    questions_raw = data.get("questions", [])
    if not isinstance(questions_raw, list) or not questions_raw:
        raise ValueError("LLM response missing 'questions' array.")

    validated = []
    for i, q in enumerate(questions_raw):
        try:
            # Ensure 4 options
            options = q.get("options", [])
            if len(options) != 4:
                logger.warning("Question %d has %d options, expected 4.", i, len(options))
                continue

            # Ensure correct_answer is valid
            correct = q.get("correct_answer", "").strip().upper()
            if correct not in ("A", "B", "C", "D"):
                logger.warning("Question %d has invalid correct_answer: %s", i, correct)
                continue

            validated.append(
                QuizQuestion(
                    question=q.get("question", ""),
                    options=options,
                    correct_answer=correct,
                    explanation=q.get("explanation", ""),
                    source_label=q.get("source_label", ""),
                )
            )
        except Exception as exc:
            logger.warning("Skipping invalid question %d: %s", i, exc)

    return validated


@router.post(
    "/quiz",
    response_model=QuizResponse,
    summary="Generate a quiz from your documents",
)
async def generate_quiz(request: QuizRequest):
    """
    Generate a structured multiple-choice quiz from uploaded documents.

    Uses RAG retrieval to gather relevant content, then prompts the LLM
    to create quiz questions in JSON format.  Each question is
    schema-validated before being returned.
    """
    # ── 1. Determine what to search for ────────────────────────
    search_query = request.topic or "key concepts and important topics"

    try:
        query_vector = embed_query(search_query)
    except Exception as exc:
        logger.error("Embedding failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to embed query: {exc}",
        )

    # ── 2. Retrieve context chunks ─────────────────────────────
    try:
        chunks = qdrant_retrieval_service.search(
            query_vector=query_vector,
            top_k=6,  # concise context window for quiz generation
            doc_id=request.doc_id,
            student_id=request.student_id,
            course_id=request.course_id,
        )
    except Exception as exc:
        logger.error("Qdrant search failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vector search unavailable: {exc}",
        )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No content found to generate a quiz from.",
        )

    # ── 3. Generate quiz via LLM ───────────────────────────────
    messages = build_quiz_messages(
        chunks=chunks,
        num_questions=request.num_questions,
        topic=request.topic,
    )

    try:
        raw_response = llm_client.chat_json(messages=messages, max_tokens=4096)
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Quiz generation failed: {exc}",
        )

    # ── 4. Validate and return ─────────────────────────────────
    try:
        questions = _validate_quiz_json(raw_response, request.num_questions)
    except ValueError as exc:
        logger.error("Quiz validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM returned invalid quiz format: {exc}",
        )

    if not questions:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM returned no valid quiz questions.",
        )

    # Collect source document names
    source_docs = list(set(
        c.get("original_filename", "") for c in chunks
        if c.get("original_filename")
    ))

    logger.info(
        "Generated quiz with %d questions from %d chunks.",
        len(questions), len(chunks),
    )

    return QuizResponse(
        questions=questions,
        topic=request.topic,
        source_documents=source_docs,
        chunks_used=len(chunks),
    )
