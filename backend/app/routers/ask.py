"""
Ask router — RAG-powered Q&A endpoint.

POST /ask
  - Embeds the student's question
  - Retrieves top-k relevant chunks from Qdrant (with metadata filtering)
  - Sends context + question to the LLM for a grounded answer
  - Returns the answer with citations tracing back to specific pages/slides
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from backend.app.config import settings
from backend.app.models.retrieval import (
    AskRequest,
    AskResponse,
    Citation,
)
from backend.app.services.embedding_service import embed_query
from backend.app.services.qdrant_service import qdrant_retrieval_service
from backend.app.services.llm_client import llm_client
from backend.app.utils.prompts import build_qa_messages

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Q&A"])


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a question about your documents",
)
async def ask_question(request: AskRequest):
    """
    RAG pipeline: embed query → retrieve context → LLM answer.

    Retrieval can be scoped to a specific document, student, or course
    via optional filters.  The answer includes page/slide-level citations.
    """
    question = request.question.strip()

    # ── 1. Embed the query ─────────────────────────────────────
    try:
        query_vector = embed_query(question)
    except Exception as exc:
        logger.error("Embedding failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to embed query: {exc}",
        )

    # ── 2. Retrieve relevant chunks ────────────────────────────
    try:
        chunks = qdrant_retrieval_service.search(
            query_vector=query_vector,
            top_k=request.top_k,
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
        return AskResponse(
            answer=(
                "I couldn't find any relevant content in your documents to "
                "answer this question. Please make sure you've uploaded "
                "documents related to your query and that they've finished "
                "processing."
            ),
            citations=[],
            chunks_used=0,
        )

    # ── 3. Build citations from retrieved chunks ───────────────
    citations = [
        Citation(
            source_label=chunk.get("source_label", f"Chunk {i + 1}"),
            doc_id=chunk.get("doc_id", ""),
            original_filename=chunk.get("original_filename", ""),
            page_number=chunk.get("page_number"),
            slide_number=chunk.get("slide_number"),
            slide_title=chunk.get("slide_title"),
            chunk_index=chunk.get("chunk_index", 0),
            relevance_score=round(chunk.get("score", 0.0), 4),
        )
        for i, chunk in enumerate(chunks)
    ]

    # ── 4. Call the LLM with context ───────────────────────────
    messages = build_qa_messages(question, chunks)

    try:
        answer = llm_client.chat(
            messages=messages,
            max_tokens=2048,
        )
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM service error: {exc}",
        )

    logger.info(
        "Answered question with %d chunks (doc_id=%s, course_id=%s).",
        len(chunks),
        request.doc_id,
        request.course_id,
    )

    return AskResponse(
        answer=answer,
        citations=citations,
        chunks_used=len(chunks),
    )
