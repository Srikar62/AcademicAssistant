"""
Documents router — status polling and document listing.

GET  /documents            → list all tracked documents
GET  /documents/{id}/status → poll processing status for a single document
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, status

from backend.app.models.document import DocumentStatusResponse
from backend.app.services.document_service import document_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get(
    "",
    response_model=List[DocumentStatusResponse],
    summary="List all documents",
)
async def list_documents():
    """Return all tracked documents, most recent first."""
    docs = document_service.list_all()
    return [
        DocumentStatusResponse(
            doc_id=d.doc_id,
            filename=d.original_filename,
            status=d.status,
            error_message=d.error_message,
            chunk_count=d.chunk_count,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in docs
    ]


@router.get(
    "/{doc_id}",
    response_model=DocumentStatusResponse,
    summary="Get document processing status (alias)",
)
@router.get(
    "/{doc_id}/status",
    response_model=DocumentStatusResponse,
    summary="Get document processing status",
)
async def get_document_status(doc_id: str):
    """
    Poll the current processing status of a document.

    Status lifecycle:
      uploading → uploaded → processing → processed
                                        ↘ failed
    """
    doc = document_service.get(doc_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found.",
        )

    return DocumentStatusResponse(
        doc_id=doc.doc_id,
        filename=doc.original_filename,
        status=doc.status,
        error_message=doc.error_message,
        chunk_count=doc.chunk_count,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )
