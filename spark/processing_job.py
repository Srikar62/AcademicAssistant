"""
Spark Structured Streaming processing job.

Consumes messages from the `documents.uploaded` Kafka topic and for each
document:
  1. Downloads the file from MinIO
  2. Parses it (PDF / PPTX / TXT)
  3. Chunks the text (sentence-aware, ~400 tokens, 15% overlap)
  4. Embeds chunks using sentence-transformers (model reused across rows)
  5. Writes embedded chunks to Qdrant
  6. Publishes a completion message to `documents.processed`
     (or `documents.failed` for errors)

Usage:
    spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4 \\
        spark/processing_job.py

    Or for local development without a Spark cluster:
        python -m spark.processing_job
"""

import json
import logging
import sys
import time
import traceback
from datetime import datetime
from typing import Optional

from minio import Minio
from kafka import KafkaProducer

from spark.config import config
from spark.parsers.base import get_parser
from spark.chunker import chunk_sections, chunk_pptx_sections
from spark.embedder import embed_chunks_batch
from spark.qdrant_writer import QdrantWriter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  Infrastructure clients
# ═══════════════════════════════════════════════════════════════


def _get_minio_client() -> Minio:
    """Create a MinIO client from config."""
    return Minio(
        endpoint=config.MINIO_ENDPOINT,
        access_key=config.MINIO_ACCESS_KEY,
        secret_key=config.MINIO_SECRET_KEY,
        secure=config.MINIO_SECURE,
    )


def _get_kafka_producer() -> Optional[KafkaProducer]:
    """Create a Kafka producer for publishing completion/failure events."""
    try:
        return KafkaProducer(
            bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            retries=3,
        )
    except Exception as exc:
        logger.warning("Could not create Kafka producer: %s", exc)
        return None


def _publish_event(
    producer: Optional[KafkaProducer],
    topic: str,
    doc_id: str,
    payload: dict,
) -> None:
    """Publish an event to Kafka (best-effort)."""
    if producer is None:
        logger.warning("No Kafka producer — skipping publish to %s", topic)
        return
    try:
        future = producer.send(topic, key=doc_id, value=payload)
        future.get(timeout=10)
        logger.info("Published to %s for doc %s.", topic, doc_id)
    except Exception as exc:
        logger.error("Failed to publish to %s: %s", topic, exc)


# ═══════════════════════════════════════════════════════════════
#  Document processing pipeline
# ═══════════════════════════════════════════════════════════════


def download_from_minio(minio_client: Minio, storage_path: str) -> bytes:
    """
    Download a file from MinIO.

    Args:
        minio_client: MinIO client instance.
        storage_path: Path in format "bucket/object_name".

    Returns:
        Raw file bytes.
    """
    parts = storage_path.split("/", 1)
    bucket = parts[0]
    object_name = parts[1]

    response = minio_client.get_object(bucket, object_name)
    try:
        file_bytes = response.read()
    finally:
        response.close()
        response.release_conn()

    logger.info("Downloaded %s (%d bytes).", storage_path, len(file_bytes))
    return file_bytes


def process_document(
    message: dict,
    minio_client: Minio,
    qdrant_writer: QdrantWriter,
    model_name: str = None,
) -> dict:
    """
    Full processing pipeline for a single document.

    Args:
        message: The Kafka message payload (DocumentUploadedMessage).
        minio_client: MinIO client for file download.
        qdrant_writer: Qdrant writer for storing embeddings.
        model_name: Override for the embedding model name.

    Returns:
        Result dict with keys: doc_id, status, chunk_count, error.
    """
    doc_id = message["doc_id"]
    file_type = message["file_type"]
    storage_path = message["storage_path"]
    original_filename = message.get("original_filename", "unknown")
    student_id = message.get("student_id", "anonymous")
    course_id = message.get("course_id", "general")

    model = model_name or config.EMBEDDING_MODEL

    logger.info(
        "Processing doc %s (%s) from %s …",
        doc_id, file_type, storage_path,
    )

    try:
        # ── 1. Download ────────────────────────────────────────
        file_bytes = download_from_minio(minio_client, storage_path)

        # ── 2. Parse ──────────────────────────────────────────
        parser = get_parser(file_type)
        sections = parser.parse(file_bytes, original_filename)
        logger.info("Doc %s: parsed %d sections.", doc_id, len(sections))

        # ── 3. Chunk ──────────────────────────────────────────
        if file_type.lower() == ".pptx":
            chunks = chunk_pptx_sections(
                sections,
                max_tokens=config.CHUNK_MAX_TOKENS,
                overlap_fraction=config.CHUNK_OVERLAP_FRACTION,
            )
        else:
            chunks = chunk_sections(
                sections,
                max_tokens=config.CHUNK_MAX_TOKENS,
                overlap_fraction=config.CHUNK_OVERLAP_FRACTION,
            )
        logger.info("Doc %s: created %d chunks.", doc_id, len(chunks))

        if not chunks:
            raise ValueError("Document produced zero chunks after parsing.")

        # ── 4. Embed ──────────────────────────────────────────
        chunks_data = [
            {
                "text": c.text,
                "chunk_index": c.chunk_index,
                "token_count": c.token_count,
                "source_label": c.source_label,
                "source_indices": c.source_indices,
                "metadata": c.metadata,
            }
            for c in chunks
        ]
        chunks_data = embed_chunks_batch(
            chunks_data, model_name=model, batch_size=64
        )
        logger.info("Doc %s: embedded %d chunks.", doc_id, len(chunks_data))

        # ── 5. Write to Qdrant ────────────────────────────────
        qdrant_writer.ensure_collection()
        upserted = qdrant_writer.upsert_chunks(
            chunks=chunks_data,
            doc_id=doc_id,
            student_id=student_id,
            course_id=course_id,
            original_filename=original_filename,
        )

        logger.info(
            "Doc %s: processing complete (%d chunks stored).",
            doc_id, upserted,
        )
        return {
            "doc_id": doc_id,
            "status": "processed",
            "chunk_count": upserted,
            "error": None,
        }

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.error(
            "Doc %s FAILED: %s\n%s",
            doc_id, error_msg, traceback.format_exc(),
        )
        return {
            "doc_id": doc_id,
            "status": "failed",
            "chunk_count": 0,
            "error": error_msg,
        }


# ═══════════════════════════════════════════════════════════════
#  Spark Structured Streaming entry point
# ═══════════════════════════════════════════════════════════════


def run_spark_streaming():
    """
    Start the Spark Structured Streaming job.

    Reads from `documents.uploaded`, processes each document in
    foreachBatch, and publishes results to `documents.processed`
    or `documents.failed`.
    """
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col, from_json, schema_of_json
    from pyspark.sql.types import (
        StructType,
        StructField,
        StringType,
    )

    # ── Spark session ──────────────────────────────────────────
    spark = (
        SparkSession.builder
        .appName(config.SPARK_APP_NAME)
        .config("spark.jars.packages",
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    logger.info("Spark session created: %s", spark.sparkContext.appName)

    # ── Message schema ─────────────────────────────────────────
    message_schema = StructType([
        StructField("doc_id", StringType(), False),
        StructField("student_id", StringType(), True),
        StructField("course_id", StringType(), True),
        StructField("storage_path", StringType(), False),
        StructField("file_type", StringType(), False),
        StructField("original_filename", StringType(), True),
        StructField("timestamp", StringType(), True),
    ])

    # ── Read from Kafka ────────────────────────────────────────
    kafka_df = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", config.KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", config.KAFKA_TOPIC_UPLOADED)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )

    # Parse the JSON value
    parsed_df = (
        kafka_df
        .select(
            col("key").cast("string").alias("doc_key"),
            from_json(col("value").cast("string"), message_schema).alias("msg"),
        )
        .select("doc_key", "msg.*")
    )

    # ── Infrastructure clients (created once on the driver) ────
    minio_client = _get_minio_client()
    qdrant_writer = QdrantWriter()
    kafka_producer = _get_kafka_producer()

    def process_batch(batch_df, batch_id):
        """Process each micro-batch of uploaded documents."""
        rows = batch_df.collect()
        if not rows:
            return

        logger.info(
            "Processing batch %d with %d document(s).",
            batch_id, len(rows),
        )

        for row in rows:
            message = row.asDict()

            result = process_document(
                message=message,
                minio_client=minio_client,
                qdrant_writer=qdrant_writer,
            )

            # Publish result to the appropriate topic
            if result["status"] == "processed":
                _publish_event(
                    kafka_producer,
                    config.KAFKA_TOPIC_PROCESSED,
                    result["doc_id"],
                    {
                        "doc_id": result["doc_id"],
                        "chunk_count": result["chunk_count"],
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
            else:
                _publish_event(
                    kafka_producer,
                    config.KAFKA_TOPIC_FAILED,
                    result["doc_id"],
                    {
                        "doc_id": result["doc_id"],
                        "error": result["error"],
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

    # ── Start streaming query ──────────────────────────────────
    query = (
        parsed_df.writeStream
        .foreachBatch(process_batch)
        .option("checkpointLocation", config.SPARK_CHECKPOINT_DIR)
        .trigger(processingTime="10 seconds")
        .start()
    )

    logger.info("Streaming query started. Waiting for termination …")
    query.awaitTermination()


# ═══════════════════════════════════════════════════════════════
#  Standalone mode (for local dev without a full Spark cluster)
# ═══════════════════════════════════════════════════════════════


def run_standalone_consumer():
    """
    Simple Kafka consumer loop for local development without Spark.

    Processes documents sequentially using the same pipeline functions
    but without distributed execution.
    """
    from kafka import KafkaConsumer

    logger.info("Starting standalone consumer (no Spark) …")

    consumer = KafkaConsumer(
        config.KAFKA_TOPIC_UPLOADED,
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        group_id=config.KAFKA_CONSUMER_GROUP,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )

    minio_client = _get_minio_client()
    qdrant_writer = QdrantWriter()
    kafka_producer = _get_kafka_producer()

    logger.info(
        "Listening on '%s' …", config.KAFKA_TOPIC_UPLOADED
    )

    try:
        while True:
            try:
                for msg in consumer:
                    message = msg.value
                    logger.info("Received: %s", message.get("doc_id", "unknown"))

                    result = process_document(
                        message=message,
                        minio_client=minio_client,
                        qdrant_writer=qdrant_writer,
                    )

                    if result["status"] == "processed":
                        _publish_event(
                            kafka_producer,
                            config.KAFKA_TOPIC_PROCESSED,
                            result["doc_id"],
                            {
                                "doc_id": result["doc_id"],
                                "chunk_count": result["chunk_count"],
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                        )
                    else:
                        _publish_event(
                            kafka_producer,
                            config.KAFKA_TOPIC_FAILED,
                            result["doc_id"],
                            {
                                "doc_id": result["doc_id"],
                                "error": result["error"],
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                        )
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                logger.warning("Consumer loop notice (%s); staying active...", exc)
                time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Consumer stopped by user.")
    finally:
        consumer.close()
        if kafka_producer:
            kafka_producer.close()


# ═══════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "standalone"

    if mode == "spark":
        run_spark_streaming()
    elif mode == "standalone":
        run_standalone_consumer()
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python -m spark.processing_job [spark|standalone]")
        sys.exit(1)
