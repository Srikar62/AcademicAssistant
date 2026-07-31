"""
Document service — in-memory document tracking.

This is an intentionally simple in-memory store for document metadata
and lifecycle status.  It keeps the API functional without requiring a
database during early development.

NOTE: Replace with a persistent store (PostgreSQL, Redis) before
      deploying beyond local dev.  The interface is deliberately thin
      so swapping the backing store is a one-file change.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, List

from backend.app.models.document import DocumentRecord, DocumentStatus

logger = logging.getLogger(__name__)


class DocumentService:
    """Track document metadata and lifecycle status."""

    def __init__(self) -> None:
        self._documents: Dict[str, DocumentRecord] = {}

    # ── CRUD ───────────────────────────────────────────────────

    def create(self, doc: DocumentRecord) -> DocumentRecord:
        """Register a new document."""
        self._documents[doc.doc_id] = doc
        logger.info("Document created: %s (%s)", doc.doc_id, doc.original_filename)
        return doc

    def get(self, doc_id: str) -> Optional[DocumentRecord]:
        """Retrieve a document by its ID, or None if not found."""
        return self._documents.get(doc_id)

    def list_all(self) -> List[DocumentRecord]:
        """Return all tracked documents (most recent first)."""
        return sorted(
            self._documents.values(),
            key=lambda d: d.created_at,
            reverse=True,
        )

    # ── Status transitions ─────────────────────────────────────

    def update_status(
        self,
        doc_id: str,
        status: DocumentStatus,
        *,
        error_message: Optional[str] = None,
        chunk_count: int = 0,
    ) -> Optional[DocumentRecord]:
        """
        Transition a document to a new status.

        Returns the updated record, or None if the doc_id doesn't exist.
        """
        doc = self._documents.get(doc_id)
        if doc is None:
            logger.warning("Attempted status update on unknown doc: %s", doc_id)
            return None

        doc.status = status
        doc.updated_at = datetime.utcnow()
        if error_message is not None:
            doc.error_message = error_message
        if chunk_count:
            doc.chunk_count = chunk_count

        logger.info("Document %s → %s", doc_id, status.value)
        return doc

    def set_storage_path(self, doc_id: str, path: str) -> None:
        """Record the MinIO storage path after upload completes."""
        doc = self._documents.get(doc_id)
        if doc:
            doc.storage_path = path
            doc.updated_at = datetime.utcnow()


# ── Module-level singleton ─────────────────────────────────────
document_service = DocumentService()
