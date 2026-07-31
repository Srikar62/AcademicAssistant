"""
Summarize router — map-reduce summarization of documents.

POST /summarize
  - Retrieves chunks from Qdrant
  - Map step: summarizes each chunk group independently
  - Reduce step: synthesizes partial summaries into a final summary
  - Returns the summary with key point highlights
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, status

from backend.app.models.generation import SummarizeRequest, SummarizeResponse
from backend.app.services.embedding_service import embed_query
from backend.app.services.qdrant_service import qdrant_retrieval_service
from backend.app.services.llm_client import llm_client
from backend.app.utils.prompts import (
    build_summarize_map_messages,
    build_summarize_reduce_messages,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Generation"])

# Maximum chunks to process in a single map step
_MAP_BATCH_SIZE = 5


def _group_chunks(chunks: List[dict], batch_size: int) -> List[str]:
    """
    Group chunks into batches and concatenate their text for the map step.

    Returns a list of concatenated text blocks.
    """
    groups = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        combined = "\n\n".join(
            f"[{c.get('source_label', 'unknown')}] {c['text']}"
            for c in batch
        )
        groups.append(combined)
    return groups


@router.post(
    "/summarize",
    response_model=SummarizeResponse,
    summary="Summarize your documents",
)
async def summarize_documents(request: SummarizeRequest):
    """
    Map-reduce summarization pipeline.

    For short documents (≤3 chunks), skips the map step and summarizes
    directly.  For longer documents, runs map-reduce:
      1. Map: independently summarize each group of 3 chunks
      2. Reduce: synthesize all partial summaries into a final summary
    """
    # ── 1. Determine what to search for ────────────────────────
    search_query = request.topic or "main content summary key concepts"

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
        if request.doc_id:
            # Full-file summarization: retrieve ALL sequential chunks for the document
            chunks = qdrant_retrieval_service.get_document_chunks(
                doc_id=request.doc_id,
                limit=250,
            )
        else:
            chunks = []

        # Fallback to vector search if doc_id was not provided or scrolling returned empty
        if not chunks:
            chunks = qdrant_retrieval_service.search(
                query_vector=query_vector,
                top_k=15,
                student_id=request.student_id,
                course_id=request.course_id,
            )
    except Exception as exc:
        logger.error("Chunk retrieval failed for summarization: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chunk retrieval unavailable: {exc}",
        )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No content found to summarize.",
        )

    # ── 3. Map step (or skip for short docs) ───────────────────
    chunk_groups = _group_chunks(chunks, _MAP_BATCH_SIZE)
    section_summaries: List[str] = []

    if len(chunk_groups) <= 1:
        # Short document — skip map step, go straight to reduce
        section_summaries = [
            chunk_groups[0] if chunk_groups else ""
        ]
    else:
        # Map: summarize each chunk group independently
        for i, group_text in enumerate(chunk_groups):
            try:
                messages = build_summarize_map_messages(group_text)
                summary = llm_client.chat(messages=messages, max_tokens=1024)
                section_summaries.append(summary)
                logger.info("Map step %d/%d complete.", i + 1, len(chunk_groups))
            except Exception as exc:
                logger.warning("Map step %d failed: %s", i + 1, exc)
                # Fall back to raw text if LLM fails for this batch
                section_summaries.append(group_text[:500] + "...")

    # ── 4. Reduce step ────────────────────────────────────────
    try:
        reduce_messages = build_summarize_reduce_messages(
            section_summaries=section_summaries,
            length=request.max_length,
            topic=request.topic,
        )
        result = llm_client.chat_json(
            messages=reduce_messages, max_tokens=4096
        )
    except Exception as exc:
        logger.error("Reduce step failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Summarization failed: {exc}",
        )

    # ── 5. Parse and return ────────────────────────────────────
    summary_text = result.get("summary", "")
    key_points = result.get("key_points", [])

    if not summary_text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM returned an empty summary.",
        )

    # Ensure key_points is a list of strings
    if not isinstance(key_points, list):
        key_points = []
    key_points = [str(kp) for kp in key_points if kp]

    source_docs = list(set(
        c.get("original_filename", "") for c in chunks
        if c.get("original_filename")
    ))

    logger.info(
        "Summarized %d chunks (%d map groups) → %d key points.",
        len(chunks), len(chunk_groups), len(key_points),
    )

    return SummarizeResponse(
        summary=summary_text,
        key_points=key_points,
        source_documents=source_docs,
        chunks_used=len(chunks),
    )
