"""
Generation models — Pydantic schemas for quiz, summary, and mind map endpoints.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
#  Quiz
# ═══════════════════════════════════════════════════════════════


class QuizQuestion(BaseModel):
    """A single multiple-choice quiz question."""
    question: str = Field(description="The question text.")
    options: List[str] = Field(
        description="Four answer options (A through D).",
        min_length=4, max_length=4,
    )
    correct_answer: str = Field(
        description="The correct option letter (A, B, C, or D).",
    )
    explanation: str = Field(
        description="Brief explanation of why the answer is correct.",
    )
    source_label: str = Field(
        default="",
        description="Source chunk label (e.g. 'Page 3').",
    )


class QuizRequest(BaseModel):
    """Payload for the /quiz endpoint."""
    doc_id: Optional[str] = Field(
        default=None,
        description="Generate quiz from a specific document.",
    )
    course_id: Optional[str] = Field(
        default=None,
        description="Generate quiz from a specific course.",
    )
    student_id: Optional[str] = Field(
        default=None,
        description="Scope to a specific student's documents.",
    )
    topic: Optional[str] = Field(
        default=None,
        description="Focus the quiz on a specific topic.",
    )
    num_questions: int = Field(
        default=5, ge=1, le=20,
        description="Number of questions to generate.",
    )


class QuizResponse(BaseModel):
    """Response from the /quiz endpoint."""
    questions: List[QuizQuestion]
    topic: Optional[str] = None
    source_documents: List[str] = Field(
        default_factory=list,
        description="Filenames of documents used to generate the quiz.",
    )
    chunks_used: int = 0


# ═══════════════════════════════════════════════════════════════
#  Summarization
# ═══════════════════════════════════════════════════════════════


class SummarizeRequest(BaseModel):
    """Payload for the /summarize endpoint."""
    doc_id: Optional[str] = Field(
        default=None,
        description="Summarize a specific document.",
    )
    course_id: Optional[str] = Field(
        default=None,
        description="Summarize documents from a specific course.",
    )
    student_id: Optional[str] = Field(
        default=None,
        description="Scope to a specific student's documents.",
    )
    topic: Optional[str] = Field(
        default=None,
        description="Focus the summary on a specific topic.",
    )
    max_length: str = Field(
        default="medium",
        description="Summary length: 'brief', 'medium', or 'detailed'.",
    )


class SummarizeResponse(BaseModel):
    """Response from the /summarize endpoint."""
    summary: str = Field(description="The generated summary.")
    key_points: List[str] = Field(
        default_factory=list,
        description="Extracted key points / bullet highlights.",
    )
    source_documents: List[str] = Field(
        default_factory=list,
        description="Filenames of documents used.",
    )
    chunks_used: int = 0


# ═══════════════════════════════════════════════════════════════
#  Mind Map
# ═══════════════════════════════════════════════════════════════


class MindMapNode(BaseModel):
    """A single node in the mind map hierarchy."""
    label: str = Field(description="Node text/label.")
    children: List["MindMapNode"] = Field(
        default_factory=list,
        description="Child nodes.",
    )


class MindMapRequest(BaseModel):
    """Payload for the /mindmap endpoint."""
    doc_id: Optional[str] = Field(
        default=None,
        description="Generate mind map from a specific document.",
    )
    course_id: Optional[str] = Field(
        default=None,
        description="Generate mind map from a specific course.",
    )
    student_id: Optional[str] = Field(
        default=None,
        description="Scope to a specific student's documents.",
    )
    topic: Optional[str] = Field(
        default=None,
        description="Focus the mind map on a specific topic.",
    )


class MindMapResponse(BaseModel):
    """Response from the /mindmap endpoint."""
    mermaid_syntax: str = Field(
        description="Mermaid mindmap syntax ready for rendering.",
    )
    root: MindMapNode = Field(
        description="The mind map as a structured tree.",
    )
    source_documents: List[str] = Field(
        default_factory=list,
        description="Filenames of documents used.",
    )
    chunks_used: int = 0


# Rebuild model for self-referencing
MindMapNode.model_rebuild()
