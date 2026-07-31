"""
Qdrant writer — batched upsert of embedded chunks to the vector database.

Creates the collection on first use if it doesn't exist, then upserts
points with full metadata for downstream retrieval filtering.
"""

import logging
import uuid
from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from spark.config import config

logger = logging.getLogger(__name__)


class QdrantWriter:
    """Manages Qdrant collection creation and batched chunk upserts."""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection_name: str = None,
        embedding_dimension: int = None,
    ):
        self.host = host or config.QDRANT_HOST
        self.port = port or config.QDRANT_PORT
        self.collection_name = collection_name or config.QDRANT_COLLECTION
        self.embedding_dimension = embedding_dimension or config.EMBEDDING_DIMENSION

        self.client = QdrantClient(host=self.host, port=self.port, check_compatibility=False)

    def ensure_collection(self) -> None:
        """Create the collection if it doesn't already exist."""
        collections = [
            c.name for c in self.client.get_collections().collections
        ]

        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                "Created Qdrant collection '%s' (dim=%d, cosine).",
                self.collection_name,
                self.embedding_dimension,
            )
        else:
            logger.info(
                "Qdrant collection '%s' already exists.",
                self.collection_name,
            )

    def upsert_chunks(
        self,
        chunks: List[dict],
        doc_id: str,
        student_id: str = "",
        course_id: str = "",
        original_filename: str = "",
        batch_size: int = 100,
    ) -> int:
        """
        Upsert embedded chunks to Qdrant with full metadata.

        Args:
            chunks: List of dicts with keys: text, embedding, chunk_index,
                    source_label, source_indices, metadata.
            doc_id: The document ID these chunks belong to.
            student_id: Student who uploaded the document.
            course_id: Course the document belongs to.
            original_filename: Original name of the uploaded file.
            batch_size: Number of points to upsert per API call.

        Returns:
            Number of points successfully upserted.
        """
        if not chunks:
            return 0

        points: List[PointStruct] = []
        for chunk in chunks:
            point_id = str(uuid.uuid4())
            payload = {
                "doc_id": doc_id,
                "student_id": student_id,
                "course_id": course_id,
                "original_filename": original_filename,
                "chunk_index": chunk.get("chunk_index", 0),
                "text": chunk["text"],
                "token_count": chunk.get("token_count", 0),
                "source_label": chunk.get("source_label", ""),
                "source_indices": chunk.get("source_indices", []),
            }
            # Merge any extra metadata from the parser
            if "metadata" in chunk:
                payload.update(chunk["metadata"])

            points.append(
                PointStruct(
                    id=point_id,
                    vector=chunk["embedding"],
                    payload=payload,
                )
            )

        # ── Batched upsert ─────────────────────────────────────
        total_upserted = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )
            total_upserted += len(batch)
            logger.debug(
                "Upserted batch %d–%d (%d points) for doc %s.",
                i,
                i + len(batch),
                len(batch),
                doc_id,
            )

        logger.info(
            "Upserted %d chunks for doc '%s' to collection '%s'.",
            total_upserted,
            doc_id,
            self.collection_name,
        )
        return total_upserted
