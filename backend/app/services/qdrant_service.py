"""
Qdrant retrieval service — handles vector search with metadata filtering.

Responsibilities:
  - Connect to Qdrant and ensure the collection exists
  - Search for similar chunks using cosine similarity
  - Apply metadata filters (doc_id, student_id, course_id)
  - Return results with citation metadata
"""

import logging
from typing import List, Optional, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    VectorParams,
)

from backend.app.config import settings

logger = logging.getLogger(__name__)


class QdrantRetrievalService:
    """Vector search over embedded document chunks."""

    def __init__(self) -> None:
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
            check_compatibility=False,
        )
        self.collection = settings.QDRANT_COLLECTION

    def ensure_collection(self) -> None:
        """Create the collection if it doesn't already exist."""
        collections = [
            c.name for c in self.client.get_collections().collections
        ]
        if self.collection not in collections:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection: %s", self.collection)

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        doc_id: Optional[str] = None,
        student_id: Optional[str] = None,
        course_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for the most similar chunks to a query vector.

        Args:
            query_vector: The embedded query (list of floats).
            top_k: Number of results to return.
            doc_id: Filter to a specific document.
            student_id: Filter to a specific student's documents.
            course_id: Filter to a specific course's documents.

        Returns:
            List of dicts with keys: text, score, source_label, doc_id,
            original_filename, and any parser metadata (page_number, etc.)
        """
        # ── Build metadata filter ──────────────────────────────
        conditions = []
        if doc_id:
            conditions.append(
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id))
            )
        if student_id:
            conditions.append(
                FieldCondition(key="student_id", match=MatchValue(value=student_id))
            )
        if course_id:
            conditions.append(
                FieldCondition(key="course_id", match=MatchValue(value=course_id))
            )

        search_filter = Filter(must=conditions) if conditions else None

        # ── Search ─────────────────────────────────────────────
        try:
            results = self.client.search(
                collection_name=self.collection,
                query_vector=query_vector,
                query_filter=search_filter,
                limit=top_k,
                with_payload=True,
            )
        except Exception as exc:
            if "404" in str(exc) or "Not Found" in str(exc):
                logger.info("Collection '%s' missing on search, attempting to auto-create...", self.collection)
                self.ensure_collection()
                return []
            raise exc

        # ── Format results ─────────────────────────────────────
        hits: List[Dict[str, Any]] = []
        for point in results:
            payload = point.payload or {}
            hits.append({
                "text": payload.get("text", ""),
                "score": point.score,
                "doc_id": payload.get("doc_id", ""),
                "original_filename": payload.get("original_filename", ""),
                "source_label": payload.get("source_label", ""),
                "chunk_index": payload.get("chunk_index", 0),
                "page_number": payload.get("page_number"),
                "slide_number": payload.get("slide_number"),
                "slide_title": payload.get("slide_title"),
            })

        logger.info(
            "Search returned %d results (top score=%.3f).",
            len(hits),
            hits[0]["score"] if hits else 0.0,
        )
        return hits

    def get_document_chunks(
        self,
        doc_id: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all chunks belonging to a specific document, sorted by chunk_index.
        Allows full-file map-reduce processing.
        """
        conditions = [
            FieldCondition(key="doc_id", match=MatchValue(value=doc_id))
        ]
        search_filter = Filter(must=conditions)
        try:
            records, _ = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=search_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            logger.error("Failed to scroll chunks for doc %s: %s", doc_id, exc)
            return []

        hits: List[Dict[str, Any]] = []
        for point in records:
            payload = point.payload or {}
            hits.append({
                "text": payload.get("text", ""),
                "score": 1.0,
                "doc_id": payload.get("doc_id", ""),
                "original_filename": payload.get("original_filename", ""),
                "source_label": payload.get("source_label", ""),
                "chunk_index": payload.get("chunk_index", 0),
                "page_number": payload.get("page_number"),
                "slide_number": payload.get("slide_number"),
                "slide_title": payload.get("slide_title"),
            })

        hits.sort(key=lambda x: x["chunk_index"])
        logger.info("Retrieved %d sequential chunks for document '%s'.", len(hits), doc_id)
        return hits


# ── Module-level singleton ─────────────────────────────────────
qdrant_retrieval_service = QdrantRetrievalService()
