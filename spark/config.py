"""
Configuration for the Spark processing pipeline.
Mirrors the backend config but lives independently so the Spark job
can run as a standalone submission without importing the FastAPI app.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class SparkPipelineConfig:
    """All settings the Spark processing job needs."""

    # ─── Kafka ─────────────────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:9092")
    KAFKA_TOPIC_UPLOADED: str = os.getenv("KAFKA_TOPIC_UPLOADED", "documents.uploaded")
    KAFKA_TOPIC_PROCESSED: str = os.getenv("KAFKA_TOPIC_PROCESSED", "documents.processed")
    KAFKA_TOPIC_FAILED: str = os.getenv("KAFKA_TOPIC_FAILED", "documents.failed")
    KAFKA_CONSUMER_GROUP: str = os.getenv("KAFKA_CONSUMER_GROUP", "spark-processing-group")

    # ─── MinIO ─────────────────────────────────────────────────
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"

    # ─── Qdrant ────────────────────────────────────────────────
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "127.0.0.1")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "academic_chunks")

    # ─── Embedding ─────────────────────────────────────────────
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_DIMENSION: int = int(os.getenv("EMBEDDING_DIMENSION", "384"))

    # ─── Chunking ──────────────────────────────────────────────
    CHUNK_MAX_TOKENS: int = int(os.getenv("CHUNK_MAX_TOKENS", "400"))
    CHUNK_OVERLAP_FRACTION: float = float(os.getenv("CHUNK_OVERLAP_FRACTION", "0.15"))

    # ─── Spark ─────────────────────────────────────────────────
    SPARK_APP_NAME: str = "AcademicAssistant-Processing"
    SPARK_CHECKPOINT_DIR: str = os.getenv(
        "SPARK_CHECKPOINT_DIR", "/tmp/academic_assistant_checkpoints"
    )


config = SparkPipelineConfig()
