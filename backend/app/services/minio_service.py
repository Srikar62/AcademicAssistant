"""
MinIO service — handles all interactions with S3-compatible object storage.

Responsibilities:
  - Ensure the upload bucket exists on startup
  - Upload files to MinIO and return the storage path
  - Generate presigned download URLs
"""

import io
import logging
from minio import Minio
from minio.error import S3Error

from backend.app.config import settings

logger = logging.getLogger(__name__)


class MinIOService:
    """Thin wrapper around the MinIO Python client."""

    def __init__(self) -> None:
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket = settings.MINIO_BUCKET

    # ── Lifecycle ──────────────────────────────────────────────

    def ensure_bucket(self) -> None:
        """Create the upload bucket if it doesn't already exist."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info("Created MinIO bucket: %s", self.bucket)
            else:
                logger.info("MinIO bucket already exists: %s", self.bucket)
        except S3Error as exc:
            logger.error("Failed to ensure MinIO bucket: %s", exc)
            raise

    # ── File Operations ────────────────────────────────────────

    def upload_file(
        self,
        object_name: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload raw bytes to MinIO.

        Args:
            object_name: The key/path to store the file under.
            file_data: The raw file bytes.
            content_type: MIME type of the file.

        Returns:
            The storage path (bucket/object_name) for the uploaded file.
        """
        try:
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=object_name,
                data=io.BytesIO(file_data),
                length=len(file_data),
                content_type=content_type,
            )
            storage_path = f"{self.bucket}/{object_name}"
            logger.info("Uploaded %s (%d bytes)", storage_path, len(file_data))
            return storage_path
        except S3Error as exc:
            logger.error("MinIO upload failed for %s: %s", object_name, exc)
            raise

    def get_presigned_url(self, object_name: str, expires_hours: int = 1) -> str:
        """Return a time-limited download URL for the given object."""
        from datetime import timedelta

        return self.client.presigned_get_object(
            bucket_name=self.bucket,
            object_name=object_name,
            expires=timedelta(hours=expires_hours),
        )


# ── Module-level singleton ─────────────────────────────────────
minio_service = MinIOService()
