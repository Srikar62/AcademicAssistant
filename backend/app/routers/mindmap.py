"""
Mind map router — generates hierarchical concept maps from documents.

POST /mindmap
  - Retrieves relevant chunks from Qdrant
  - LLM extracts a hierarchical concept tree as structured JSON
  - Server-side conversion to validated Mermaid mindmap syntax
  - Returns both the structured tree and the Mermaid syntax
"""

import logging

from fastapi import APIRouter, HTTPException, status

from backend.app.models.generation import (
    MindMapRequest,
    MindMapResponse,
    MindMapNode,
)
from backend.app.services.embedding_service import embed_query
from backend.app.services.qdrant_service import qdrant_retrieval_service
from backend.app.services.llm_client import llm_client
from backend.app.utils.prompts import build_mindmap_messages
from backend.app.utils.mermaid_converter import (
    json_to_mermaid,
    parse_mindmap_json,
    validate_mermaid_mindmap,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Generation"])


def _dict_to_node(d: dict) -> MindMapNode:
    """Recursively convert a dict tree to MindMapNode objects."""
    return MindMapNode(
        label=d.get("label", "Untitled"),
        children=[_dict_to_node(c) for c in d.get("children", [])],
    )


@router.post(
    "/mindmap",
    response_model=MindMapResponse,
    summary="Generate a mind map from your documents",
)
async def generate_mindmap(request: MindMapRequest):
    """
    Generate a hierarchical mind map from uploaded documents.

    The LLM extracts concepts as structured JSON, which is then
    deterministically converted to Mermaid mindmap syntax server-side.
    This avoids the fragile approach of having the LLM generate
    Mermaid syntax directly.
    """
    # ── 1. Determine what to search for ────────────────────────
    search_query = request.topic or "main concepts topics and relationships"

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
            top_k=6,
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
            detail="No content found to generate a mind map from.",
        )

    # ── 3. Generate mind map JSON via LLM ──────────────────────
    messages = build_mindmap_messages(chunks=chunks, topic=request.topic)

    try:
        raw_response = llm_client.chat_json(messages=messages, max_tokens=4096)
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Mind map generation failed: {exc}",
        )

    # ── 4. Parse and normalize the JSON structure ──────────────
    try:
        root_dict = parse_mindmap_json(raw_response)
    except ValueError as exc:
        logger.error("Mind map JSON invalid: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM returned invalid mind map structure: {exc}",
        )

    # ── 5. Convert to Mermaid syntax ───────────────────────────
    mermaid_syntax = json_to_mermaid(root_dict)

    if not validate_mermaid_mindmap(mermaid_syntax):
        logger.error("Generated Mermaid syntax failed validation.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Generated mind map has invalid Mermaid syntax.",
        )

    # ── 6. Build response ──────────────────────────────────────
    root_node = _dict_to_node(root_dict)

    source_docs = list(set(
        c.get("original_filename", "") for c in chunks
        if c.get("original_filename")
    ))

    logger.info(
        "Generated mind map with %d top-level concepts from %d chunks.",
        len(root_node.children), len(chunks),
    )

    return MindMapResponse(
        mermaid_syntax=mermaid_syntax,
        root=root_node,
        source_documents=source_docs,
        chunks_used=len(chunks),
    )
