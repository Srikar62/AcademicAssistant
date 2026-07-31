"""
Kafka service — manages producer lifecycle and message publishing.

Responsibilities:
  - Initialize and close the Kafka producer
  - Publish structured messages to Kafka topics
  - Create required topics if they don't exist
"""

import json
import logging
import threading
from typing import Optional

from kafka import KafkaProducer, KafkaConsumer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, NoBrokersAvailable

from backend.app.config import settings
from backend.app.services.document_service import document_service
from backend.app.models.document import DocumentStatus

logger = logging.getLogger(__name__)


class KafkaService:
    """Manages a Kafka producer and topic administration."""

    def __init__(self) -> None:
        self._producer: Optional[KafkaProducer] = None

    # ── Lifecycle ──────────────────────────────────────────────

    def connect(self) -> None:
        """
        Initialize the Kafka producer.
        Called during FastAPI startup; will retry-log but not crash the app
        so the API can still serve uploads even if Kafka is temporarily down.
        """
        try:
            self._producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=3,
                max_block_ms=5000,
            )
            logger.info(
                "Kafka producer connected to %s",
                settings.KAFKA_BOOTSTRAP_SERVERS,
            )
        except NoBrokersAvailable:
            logger.warning(
                "Kafka broker not available at %s — uploads will queue locally "
                "and fail on publish until Kafka is reachable.",
                settings.KAFKA_BOOTSTRAP_SERVERS,
            )
            self._producer = None

    def close(self) -> None:
        """Flush and close the producer gracefully."""
        if self._producer:
            self._producer.flush(timeout=10)
            self._producer.close(timeout=10)
            logger.info("Kafka producer closed.")

    # ── Publishing ─────────────────────────────────────────────

    def publish(self, topic: str, key: str, value: dict) -> bool:
        """
        Send a message to a Kafka topic.

        Args:
            topic: Target topic name.
            key: Message key (typically doc_id for partition affinity).
            value: Message payload as a dict (will be JSON-serialized).

        Returns:
            True if the message was sent successfully, False otherwise.
        """
        if self._producer is None:
            logger.error("Cannot publish — Kafka producer is not connected.")
            return False

        try:
            future = self._producer.send(topic, key=key, value=value)
            record_metadata = future.get(timeout=10)
            logger.info(
                "Published to %s [partition=%d, offset=%d]",
                record_metadata.topic,
                record_metadata.partition,
                record_metadata.offset,
            )
            return True
        except Exception as exc:
            logger.error("Failed to publish to %s: %s", topic, exc)
            return False

    # ── Topic Administration ───────────────────────────────────

    def create_topics(self) -> None:
        """
        Create the required Kafka topics if they don't already exist.
        Safe to call repeatedly — existing topics are silently skipped.
        """
        topic_names = [
            settings.KAFKA_TOPIC_UPLOADED,
            settings.KAFKA_TOPIC_PROCESSED,
            settings.KAFKA_TOPIC_FAILED,
        ]

        try:
            admin = KafkaAdminClient(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            )
            new_topics = [
                NewTopic(
                    name=name,
                    num_partitions=3,
                    replication_factor=1,
                )
                for name in topic_names
            ]
            admin.create_topics(new_topics=new_topics, validate_only=False)
            logger.info("Kafka topics created: %s", topic_names)
        except TopicAlreadyExistsError:
            logger.info("Kafka topics already exist.")
        except NoBrokersAvailable:
            logger.warning(
                "Kafka not reachable — topics will be created on next startup."
            )
        except Exception as exc:
            logger.warning("Could not create Kafka topics: %s", exc)

    def start_consumer(self) -> None:
        """Start background consumer to listen for processed/failed events."""
        def _consumer_loop():
            try:
                consumer = KafkaConsumer(
                    settings.KAFKA_TOPIC_PROCESSED,
                    settings.KAFKA_TOPIC_FAILED,
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
                    group_id="backend-status-listener",
                    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                )
                logger.info("Kafka status consumer listening on processed/failed topics.")
                for msg in consumer:
                    data = msg.value
                    doc_id = data.get("doc_id")
                    if not doc_id:
                        continue
                    if msg.topic == settings.KAFKA_TOPIC_PROCESSED:
                        chunk_count = data.get("chunk_count", 0)
                        document_service.update_status(
                            doc_id, DocumentStatus.PROCESSED, chunk_count=chunk_count
                        )
                        logger.info("Updated doc %s status → PROCESSED (%d chunks).", doc_id, chunk_count)
                    elif msg.topic == settings.KAFKA_TOPIC_FAILED:
                        err = data.get("error", "Processing failed")
                        document_service.update_status(
                            doc_id, DocumentStatus.FAILED, error_message=err
                        )
                        logger.info("Updated doc %s status → FAILED.", doc_id)
            except Exception as exc:
                logger.warning("Kafka status consumer loop stopped: %s", exc)

        t = threading.Thread(target=_consumer_loop, daemon=True)
        t.start()


# ── Module-level singleton ─────────────────────────────────────
kafka_service = KafkaService()
