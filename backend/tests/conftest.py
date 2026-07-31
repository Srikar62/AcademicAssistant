"""
Shared test fixtures for the backend test suite.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.document_service import document_service


@pytest.fixture(autouse=True)
def clear_documents():
    """Reset the in-memory document store between tests."""
    document_service._documents.clear()
    yield
    document_service._documents.clear()


@pytest.fixture
def mock_minio():
    """Patch MinIO service so no real object storage is needed."""
    with patch(
        "backend.app.routers.upload.minio_service"
    ) as mock:
        mock.upload_file.return_value = "academic-documents/anon/general/test.pdf"
        yield mock


@pytest.fixture
def mock_kafka():
    """Patch Kafka service so no broker is needed."""
    with patch(
        "backend.app.routers.upload.kafka_service"
    ) as mock:
        mock.publish.return_value = True
        yield mock


@pytest.fixture
def client():
    """FastAPI test client (no lifespan hooks — services are mocked)."""
    return TestClient(app, raise_server_exceptions=False)
