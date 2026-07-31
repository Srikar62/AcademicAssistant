"""
Retrieval models — Pydantic schemas for Q&A request/response payloads.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ─── Request ──────────────────────────────────────────────────


class AskRequest(BaseModel):
    """Payload for the /ask endpoint."""
    question: str = Field(
        ..., min_length=3, max_length=2000,
        description="The student's question.",
    )
    doc_id: Optional[str] = Field(
        default=None,
        description="Limit retrieval to a specific document.",
    )
    student_id: Optional[str] = Field(
        default=None,
        description="Limit retrieval to a specific student's uploads.",
    )
    course_id: Optional[str] = Field(
        default=None,
        description="Limit retrieval to a specific course.",
    )
    top_k: int = Field(
        default=5, ge=1, le=20,
        description="Number of context chunks to retrieve.",
    )


# ─── Citation ─────────────────────────────────────────────────


class Citation(BaseModel):
    """A single citation referencing a source chunk."""
    source_label: str = Field(
        description="E.g. 'Page 3', 'Slide 7'",
    )
    doc_id: str
    original_filename: str = ""
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    slide_title: Optional[str] = None
    chunk_index: int = 0
    relevance_score: float = 0.0


# ─── Response ─────────────────────────────────────────────────


class AskResponse(BaseModel):
    """Response from the /ask endpoint."""
    answer: str = Field(description="The grounded answer from the LLM.")
    citations: List[Citation] = Field(
        default_factory=list,
        description="Source chunks used to generate the answer.",
    )
    chunks_used: int = Field(
        description="Number of context chunks sent to the LLM.",
    )
