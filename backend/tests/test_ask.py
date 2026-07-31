"""
Tests for the /ask RAG endpoint and retrieval services.

All external services (Qdrant, embedding model, LLM) are mocked so
tests run without Docker or API keys.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.document_service import document_service


# ═══════════════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def clear_documents():
    """Reset the in-memory document store between tests."""
    document_service._documents.clear()
    yield
    document_service._documents.clear()


@pytest.fixture
def mock_embed_query():
    """Mock the embedding service to return a fake vector."""
    with patch("backend.app.routers.ask.embed_query") as mock:
        mock.return_value = [0.1] * 384
        yield mock


@pytest.fixture
def mock_qdrant_search():
    """Mock the Qdrant retrieval service search method."""
    with patch(
        "backend.app.routers.ask.qdrant_retrieval_service"
    ) as mock:
        mock.search.return_value = [
            {
                "text": "Machine learning is a subset of artificial intelligence that focuses on learning from data.",
                "score": 0.92,
                "doc_id": "doc-001",
                "original_filename": "lecture_01.pdf",
                "source_label": "Page 3",
                "chunk_index": 2,
                "page_number": 3,
                "slide_number": None,
                "slide_title": None,
            },
            {
                "text": "Supervised learning uses labeled datasets to train predictive models.",
                "score": 0.87,
                "doc_id": "doc-001",
                "original_filename": "lecture_01.pdf",
                "source_label": "Page 5",
                "chunk_index": 4,
                "page_number": 5,
                "slide_number": None,
                "slide_title": None,
            },
            {
                "text": "Neural networks are inspired by biological neural structures in the brain.",
                "score": 0.81,
                "doc_id": "doc-002",
                "original_filename": "slides.pptx",
                "source_label": "Slide 7",
                "chunk_index": 6,
                "page_number": None,
                "slide_number": 7,
                "slide_title": "Neural Networks",
            },
        ]
        yield mock


@pytest.fixture
def mock_qdrant_empty():
    """Mock Qdrant returning no results."""
    with patch(
        "backend.app.routers.ask.qdrant_retrieval_service"
    ) as mock:
        mock.search.return_value = []
        yield mock


@pytest.fixture
def mock_llm():
    """Mock the LLM client to return a canned response."""
    with patch("backend.app.routers.ask.llm_client") as mock:
        mock.chat.return_value = (
            "Machine learning is a subset of artificial intelligence that "
            "enables systems to learn from data [Source: Page 3]. It uses "
            "approaches like supervised learning, which trains models on "
            "labeled datasets [Source: Page 5]. The underlying architectures "
            "often include neural networks, which are inspired by biological "
            "neural structures [Source: Slide 7]."
        )
        yield mock


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app, raise_server_exceptions=False)


# ═══════════════════════════════════════════════════════════════
#  /ask Endpoint Tests
# ═══════════════════════════════════════════════════════════════


class TestAskEndpoint:
    """POST /ask"""

    def test_ask_success(
        self, client, mock_embed_query, mock_qdrant_search, mock_llm
    ):
        """A valid question should return a grounded answer with citations."""
        response = client.post(
            "/ask",
            json={
                "question": "What is machine learning?",
                "doc_id": "doc-001",
            },
        )
        assert response.status_code == 200
        body = response.json()

        # Answer should be present
        assert len(body["answer"]) > 0
        assert "machine learning" in body["answer"].lower()

        # Citations should trace back to chunks
        assert body["chunks_used"] == 3
        assert len(body["citations"]) == 3
        assert body["citations"][0]["source_label"] == "Page 3"
        assert body["citations"][0]["page_number"] == 3
        assert body["citations"][2]["slide_number"] == 7
        assert body["citations"][2]["slide_title"] == "Neural Networks"

        # Embedding should have been called with the question
        mock_embed_query.assert_called_once_with("What is machine learning?")

        # Qdrant search should have been called with filters
        mock_qdrant_search.search.assert_called_once()
        call_kwargs = mock_qdrant_search.search.call_args
        assert call_kwargs.kwargs.get("doc_id") == "doc-001"

    def test_ask_with_course_filter(
        self, client, mock_embed_query, mock_qdrant_search, mock_llm
    ):
        """Filters should be passed through to the search."""
        response = client.post(
            "/ask",
            json={
                "question": "What are neural networks?",
                "course_id": "cs-101",
                "student_id": "stu-001",
            },
        )
        assert response.status_code == 200

        call_kwargs = mock_qdrant_search.search.call_args
        assert call_kwargs.kwargs.get("course_id") == "cs-101"
        assert call_kwargs.kwargs.get("student_id") == "stu-001"

    def test_ask_no_results_returns_friendly_message(
        self, client, mock_embed_query, mock_qdrant_empty, mock_llm
    ):
        """When no chunks are found, return a helpful message (not an error)."""
        response = client.post(
            "/ask",
            json={"question": "What is quantum entanglement?"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "couldn't find" in body["answer"].lower()
        assert body["chunks_used"] == 0
        assert body["citations"] == []

        # LLM should NOT have been called (no context to ground on)
        mock_llm.chat.assert_not_called()

    def test_ask_custom_top_k(
        self, client, mock_embed_query, mock_qdrant_search, mock_llm
    ):
        """top_k parameter should be forwarded to the search."""
        client.post(
            "/ask",
            json={"question": "Explain deep learning", "top_k": 10},
        )
        call_kwargs = mock_qdrant_search.search.call_args
        assert call_kwargs.kwargs.get("top_k") == 10

    def test_ask_empty_question_rejected(self, client):
        """A question shorter than 3 chars should be rejected."""
        response = client.post(
            "/ask",
            json={"question": "ab"},
        )
        assert response.status_code == 422

    def test_ask_embedding_failure(
        self, client, mock_qdrant_search, mock_llm
    ):
        """If embedding fails, return 500."""
        with patch(
            "backend.app.routers.ask.embed_query",
            side_effect=RuntimeError("Model not loaded"),
        ):
            response = client.post(
                "/ask",
                json={"question": "What is ML?"},
            )
            assert response.status_code == 500

    def test_ask_qdrant_failure(
        self, client, mock_embed_query, mock_llm
    ):
        """If Qdrant is down, return 503."""
        with patch(
            "backend.app.routers.ask.qdrant_retrieval_service"
        ) as mock_qdrant:
            mock_qdrant.search.side_effect = ConnectionError("Qdrant unreachable")
            response = client.post(
                "/ask",
                json={"question": "What is ML?"},
            )
            assert response.status_code == 503

    def test_ask_llm_failure(
        self, client, mock_embed_query, mock_qdrant_search
    ):
        """If the LLM call fails, return 502."""
        with patch("backend.app.routers.ask.llm_client") as mock_llm:
            mock_llm.chat.side_effect = RuntimeError("API key invalid")
            response = client.post(
                "/ask",
                json={"question": "What is machine learning?"},
            )
            assert response.status_code == 502


# ═══════════════════════════════════════════════════════════════
#  Prompt Template Tests
# ═══════════════════════════════════════════════════════════════


class TestPromptTemplates:
    """Tests for the prompt formatting utilities."""

    def test_format_context_chunks(self):
        from backend.app.utils.prompts import format_context_chunks

        chunks = [
            {
                "text": "ML is great.",
                "source_label": "Page 1",
                "original_filename": "lecture.pdf",
                "score": 0.95,
            },
            {
                "text": "DL is even better.",
                "source_label": "Slide 3",
                "original_filename": "slides.pptx",
                "score": 0.88,
            },
        ]

        result = format_context_chunks(chunks)
        assert "Page 1" in result
        assert "Slide 3" in result
        assert "lecture.pdf" in result
        assert "ML is great." in result

    def test_build_qa_messages(self):
        from backend.app.utils.prompts import build_qa_messages

        messages = build_qa_messages(
            question="What is ML?",
            chunks=[{"text": "ML info", "source_label": "Page 1"}],
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "What is ML?" in messages[1]["content"]
        assert "ML info" in messages[1]["content"]


# ═══════════════════════════════════════════════════════════════
#  Citation Tracing Tests
# ═══════════════════════════════════════════════════════════════


class TestCitationTracing:
    """Tests that citation metadata flows correctly through the pipeline."""

    def test_citation_includes_page_numbers(
        self, client, mock_embed_query, mock_qdrant_search, mock_llm
    ):
        """Citations for PDF chunks should include page numbers."""
        response = client.post(
            "/ask",
            json={"question": "Explain machine learning"},
        )
        citations = response.json()["citations"]

        pdf_citations = [c for c in citations if c["page_number"] is not None]
        assert len(pdf_citations) >= 1
        assert pdf_citations[0]["page_number"] == 3

    def test_citation_includes_slide_info(
        self, client, mock_embed_query, mock_qdrant_search, mock_llm
    ):
        """Citations for PPTX chunks should include slide number and title."""
        response = client.post(
            "/ask",
            json={"question": "What are neural networks?"},
        )
        citations = response.json()["citations"]

        pptx_citations = [c for c in citations if c["slide_number"] is not None]
        assert len(pptx_citations) >= 1
        assert pptx_citations[0]["slide_number"] == 7
        assert pptx_citations[0]["slide_title"] == "Neural Networks"

    def test_citation_relevance_scores(
        self, client, mock_embed_query, mock_qdrant_search, mock_llm
    ):
        """Citations should include relevance scores from the vector search."""
        response = client.post(
            "/ask",
            json={"question": "Explain ML"},
        )
        citations = response.json()["citations"]

        assert citations[0]["relevance_score"] == 0.92
        assert citations[1]["relevance_score"] == 0.87
        assert citations[2]["relevance_score"] == 0.81

        # Scores should be in descending order
        scores = [c["relevance_score"] for c in citations]
        assert scores == sorted(scores, reverse=True)
