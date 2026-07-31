"""
Kafka topic setup script.

Run this standalone to create the required topics before starting the
Spark processing job.  The FastAPI app also calls this on startup, but
having a standalone script is useful for CI and manual setup.

Usage:
    python -m configs.kafka_topics
"""

import sys
import logging

from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, NoBrokersAvailable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOOTSTRAP_SERVERS = "localhost:9092"

TOPICS = [
    {"name": "documents.uploaded", "partitions": 3, "replication": 1},
    {"name": "documents.processed", "partitions": 3, "replication": 1},
    {"name": "documents.failed", "partitions": 1, "replication": 1},
]


def create_topics(bootstrap_servers: str = BOOTSTRAP_SERVERS) -> None:
    """Create all required Kafka topics."""
    try:
        admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers)
    except NoBrokersAvailable:
        logger.error(
            "Cannot connect to Kafka at %s — is the broker running?",
            bootstrap_servers,
        )
        sys.exit(1)

    new_topics = [
        NewTopic(
            name=t["name"],
            num_partitions=t["partitions"],
            replication_factor=t["replication"],
        )
        for t in TOPICS
    ]

    try:
        admin.create_topics(new_topics=new_topics, validate_only=False)
        logger.info("Created topics: %s", [t["name"] for t in TOPICS])
    except TopicAlreadyExistsError:
        logger.info("All topics already exist — nothing to do.")
    except Exception as exc:
        logger.error("Failed to create topics: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    create_topics()
