"""
Upload router — handles file uploads, stores them in MinIO,
and publishes ingestion events to Kafka.

POST /upload
  - Accepts a file (PDF, PPTX, TXT, MD) plus optional metadata
  - Validates type and size
  - Stores the file in MinIO
  - Publishes a message to `documents.uploaded`
  - Returns a doc_id the client can use to poll for status
"""

import os
import uuid
import logging

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, status

from backend.app.config import settings
from backend.app.models.document import (
    DocumentRecord,
    DocumentStatus,
    DocumentUploadedMessage,
    FileType,
    UploadResponse,
)
from backend.app.services.minio_service import minio_service
from backend.app.services.kafka_service import kafka_service
from backend.app.services.document_service import document_service
from backend.app.utils.validators import validate_upload_file, validate_file_size, validate_file_magic_bytes

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Upload"])


# ─── Content-type mapping ─────────────────────────────────────
MIME_MAP = {
    ".pdf": "application/pdf",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document for processing",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF, PPTX, TXT, or MD file"),
    student_id: str = Form(default="anonymous", description="Student identifier"),
    course_id: str = Form(default="general", description="Course identifier"),
):
    """
    Accept a document, store it in object storage, and queue it for
    processing via Kafka.  Returns immediately — the client should
    poll `/documents/{doc_id}/status` to track progress.
    """
    # ── 1. Validate ────────────────────────────────────────────
    validate_upload_file(file)
    file_data = await file.read()
    await validate_file_size(file_data)

    # Validate file content matches declared extension (magic bytes)
    ext = os.path.splitext(file.filename)[1].lower()
    validate_file_magic_bytes(file_data, ext)

    # ── 2. Build internal record ───────────────────────────────
    # ext already extracted above during magic byte validation
    doc_id = str(uuid.uuid4())
    object_name = f"{student_id}/{course_id}/{doc_id}{ext}"

    doc = DocumentRecord(
        doc_id=doc_id,
        student_id=student_id,
        course_id=course_id,
        original_filename=file.filename,
        file_type=FileType(ext),
    )
    document_service.create(doc)

    # ── 3. Upload to MinIO ─────────────────────────────────────
    try:
        storage_path = minio_service.upload_file(
            object_name=object_name,
            file_data=file_data,
            content_type=MIME_MAP.get(ext, "application/octet-stream"),
        )
        document_service.set_storage_path(doc_id, storage_path)
    except Exception as exc:
        document_service.update_status(
            doc_id, DocumentStatus.FAILED, error_message=str(exc)
        )
        logger.error("Upload to MinIO failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to store file in object storage: {exc}",
        )

    # ── 4. Publish to Kafka ────────────────────────────────────
    kafka_msg = DocumentUploadedMessage(
        doc_id=doc_id,
        student_id=student_id,
        course_id=course_id,
        storage_path=storage_path,
        file_type=ext,
        original_filename=file.filename,
    )

    published = kafka_service.publish(
        topic=settings.KAFKA_TOPIC_UPLOADED,
        key=doc_id,
        value=kafka_msg.model_dump(),
    )

    if published:
        document_service.update_status(doc_id, DocumentStatus.UPLOADED)
    else:
        # File is stored but Kafka is unreachable — mark as uploaded
        # so it can be retried.  Don't fail the request since the file
        # is safely persisted in MinIO.
        document_service.update_status(
            doc_id,
            DocumentStatus.UPLOADED,
            error_message="Kafka publish failed — will retry on recovery.",
        )
        logger.warning(
            "File %s stored in MinIO but Kafka publish failed.", doc_id
        )

    # ── 5. Return ──────────────────────────────────────────────
    return UploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        file_type=ext,
        status=doc.status,
        message="Document uploaded and queued for processing.",
    )
