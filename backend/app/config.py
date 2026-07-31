"""
Application configuration — all settings read from environment variables
with sensible defaults for local development.
"""

from typing import List, Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    """Central configuration loaded from .env / environment variables."""

    # ─── Hugging Face Token ─────────────────────────────────────
    HF_TOKEN: Optional[str] = None

    # ─── MinIO (S3-compatible object storage) ──────────────────
    MINIO_ENDPOINT: str = "127.0.0.1:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "academic-documents"
    MINIO_SECURE: bool = False

    # ─── Kafka ─────────────────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = "127.0.0.1:9092"
    KAFKA_TOPIC_UPLOADED: str = "documents.uploaded"
    KAFKA_TOPIC_PROCESSED: str = "documents.processed"
    KAFKA_TOPIC_FAILED: str = "documents.failed"

    # ─── Qdrant ────────────────────────────────────────────────
    QDRANT_HOST: str = "127.0.0.1"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "academic_chunks"

    # ─── Embedding ─────────────────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384

    # ─── App ───────────────────────────────────────────────────
    MAX_FILE_SIZE_MB: int = 50
    # Stored as comma-separated string to avoid pydantic-settings
    # JSON parsing issues with .env files.
    ALLOWED_EXTENSIONS: str = ".pdf,.pptx,.txt,.md"

    # ─── LLM ──────────────────────────────────────────────────
    LLM_API_KEY: str = "your-api-key-here"
    LLM_PROVIDER: str = "groq"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MAX_CONTEXT_CHUNKS: int = 5
    LLM_TEMPERATURE: float = 0.1

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def allowed_extensions_list(self) -> List[str]:
        """Return ALLOWED_EXTENSIONS as a list of strings."""
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]


settings = Settings()
