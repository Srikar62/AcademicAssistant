"""
Document models — Pydantic schemas for request/response payloads
and internal data structures.
"""

from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
import uuid


# ─── Enums ─────────────────────────────────────────────────────


class DocumentStatus(str, Enum):
    """Lifecycle states of a document in the pipeline."""
    UPLOADING = "uploading"
    UPLOADED = "uploaded"          # stored in MinIO, Kafka message sent
    PROCESSING = "processing"     # Spark job picked it up
    PROCESSED = "processed"       # chunks embedded and stored in Qdrant
    FAILED = "failed"             # routed to dead-letter topic


class FileType(str, Enum):
    """Supported upload file types."""
    PDF = ".pdf"
    PPTX = ".pptx"
    TXT = ".txt"
    MD = ".md"


# ─── Internal Document Record ─────────────────────────────────


class DocumentRecord(BaseModel):
    """Internal representation of a tracked document."""
    doc_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    student_id: str = "anonymous"
    course_id: str = "general"
    original_filename: str
    file_type: FileType
    storage_path: str = ""
    status: DocumentStatus = DocumentStatus.UPLOADING
    error_message: Optional[str] = None
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── API Response Schemas ──────────────────────────────────────


class UploadResponse(BaseModel):
    """Response returned after a successful file upload."""
    doc_id: str
    filename: str
    file_type: str
    status: DocumentStatus
    message: str


class DocumentStatusResponse(BaseModel):
    """Response for the status polling endpoint."""
    doc_id: str
    filename: str
    status: DocumentStatus
    error_message: Optional[str] = None
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime


# ─── Kafka Message Schema ─────────────────────────────────────


class DocumentUploadedMessage(BaseModel):
    """
    Payload published to the `documents.uploaded` Kafka topic.
    Contains everything the Spark job needs to locate and process the file.
    """
    doc_id: str
    student_id: str
    course_id: str
    storage_path: str
    file_type: str
    original_filename: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
