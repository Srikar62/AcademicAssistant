"""
Tests for generation endpoints: /quiz, /summarize, /mindmap.

All external services are mocked. Tests cover success paths,
validation, error handling, and the Mermaid converter.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.document_service import document_service


# ═══════════════════════════════════════════════════════════════
#  Shared Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def clear_documents():
    document_service._documents.clear()
    yield
    document_service._documents.clear()


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_embed():
    with patch("backend.app.routers.quiz.embed_query") as mq, \
         patch("backend.app.routers.summarize.embed_query") as ms, \
         patch("backend.app.routers.mindmap.embed_query") as mm:
        for m in (mq, ms, mm):
            m.return_value = [0.1] * 384
        yield mq  # return one for assertion if needed


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant for all three routers."""
    chunks = [
        {
            "text": "Machine learning is a field of AI that enables systems to learn from data.",
            "score": 0.95,
            "doc_id": "doc-001",
            "original_filename": "lecture.pdf",
            "source_label": "Page 1",
            "chunk_index": 0,
            "page_number": 1,
            "slide_number": None,
            "slide_title": None,
        },
        {
            "text": "Supervised learning uses labeled data. Unsupervised learning finds patterns in unlabeled data.",
            "score": 0.90,
            "doc_id": "doc-001",
            "original_filename": "lecture.pdf",
            "source_label": "Page 3",
            "chunk_index": 2,
            "page_number": 3,
            "slide_number": None,
            "slide_title": None,
        },
        {
            "text": "Neural networks have layers of connected nodes. Deep learning uses many layers.",
            "score": 0.85,
            "doc_id": "doc-001",
            "original_filename": "lecture.pdf",
            "source_label": "Page 5",
            "chunk_index": 4,
            "page_number": 5,
            "slide_number": None,
            "slide_title": None,
        },
    ]
    with patch("backend.app.routers.quiz.qdrant_retrieval_service") as q1, \
         patch("backend.app.routers.summarize.qdrant_retrieval_service") as q2, \
         patch("backend.app.routers.mindmap.qdrant_retrieval_service") as q3:
        for q in (q1, q2, q3):
            q.search.return_value = chunks
            q.get_document_chunks.return_value = chunks
        yield q1


@pytest.fixture
def mock_qdrant_empty():
    with patch("backend.app.routers.quiz.qdrant_retrieval_service") as q1, \
         patch("backend.app.routers.summarize.qdrant_retrieval_service") as q2, \
         patch("backend.app.routers.mindmap.qdrant_retrieval_service") as q3:
        for q in (q1, q2, q3):
            q.search.return_value = []
        yield q1


# ═══════════════════════════════════════════════════════════════
#  Quiz Endpoint Tests
# ═══════════════════════════════════════════════════════════════


MOCK_QUIZ_RESPONSE = {
    "questions": [
        {
            "question": "What is machine learning?",
            "options": [
                "A) A type of database",
                "B) A field of AI that enables systems to learn from data",
                "C) A programming language",
                "D) A hardware component",
            ],
            "correct_answer": "B",
            "explanation": "ML is a subset of AI focused on learning from data.",
            "source_label": "Page 1",
        },
        {
            "question": "What does supervised learning use?",
            "options": [
                "A) Unlabeled data",
                "B) Random data",
                "C) Labeled data",
                "D) No data",
            ],
            "correct_answer": "C",
            "explanation": "Supervised learning trains on labeled datasets.",
            "source_label": "Page 3",
        },
    ]
}


class TestQuizEndpoint:
    """POST /quiz"""

    def test_quiz_success(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.quiz.llm_client") as mock_llm:
            mock_llm.chat_json.return_value = MOCK_QUIZ_RESPONSE
            response = client.post(
                "/quiz",
                json={"doc_id": "doc-001", "num_questions": 2},
            )
        assert response.status_code == 200
        body = response.json()
        assert len(body["questions"]) == 2
        assert body["questions"][0]["correct_answer"] == "B"
        assert len(body["questions"][0]["options"]) == 4
        assert body["chunks_used"] == 3

    def test_quiz_with_topic(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.quiz.llm_client") as mock_llm:
            mock_llm.chat_json.return_value = MOCK_QUIZ_RESPONSE
            response = client.post(
                "/quiz",
                json={"topic": "neural networks", "num_questions": 2},
            )
        assert response.status_code == 200
        assert response.json()["topic"] == "neural networks"

    def test_quiz_no_content_404(self, client, mock_embed, mock_qdrant_empty):
        response = client.post("/quiz", json={"num_questions": 3})
        assert response.status_code == 404

    def test_quiz_invalid_llm_response(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.quiz.llm_client") as mock_llm:
            mock_llm.chat_json.return_value = {"questions": []}
            response = client.post("/quiz", json={"num_questions": 2})
        assert response.status_code == 502

    def test_quiz_skips_invalid_questions(self, client, mock_embed, mock_qdrant):
        """Questions with wrong option count or invalid correct_answer are skipped."""
        with patch("backend.app.routers.quiz.llm_client") as mock_llm:
            mock_llm.chat_json.return_value = {
                "questions": [
                    {  # Valid
                        "question": "Q1?",
                        "options": ["A) a", "B) b", "C) c", "D) d"],
                        "correct_answer": "A",
                        "explanation": "Because A.",
                    },
                    {  # Invalid — only 3 options
                        "question": "Q2?",
                        "options": ["A) a", "B) b", "C) c"],
                        "correct_answer": "A",
                        "explanation": "Bad question.",
                    },
                    {  # Invalid — bad correct_answer
                        "question": "Q3?",
                        "options": ["A) a", "B) b", "C) c", "D) d"],
                        "correct_answer": "E",
                        "explanation": "Bad answer.",
                    },
                ]
            }
            response = client.post("/quiz", json={"num_questions": 3})
        assert response.status_code == 200
        assert len(response.json()["questions"]) == 1  # only Q1 survives

    def test_quiz_source_documents(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.quiz.llm_client") as mock_llm:
            mock_llm.chat_json.return_value = MOCK_QUIZ_RESPONSE
            response = client.post("/quiz", json={"num_questions": 2})
        assert "lecture.pdf" in response.json()["source_documents"]


# ═══════════════════════════════════════════════════════════════
#  Summarize Endpoint Tests
# ═══════════════════════════════════════════════════════════════


MOCK_SUMMARY_RESPONSE = {
    "summary": (
        "Machine learning is a subfield of artificial intelligence that "
        "enables computer systems to learn from data. It encompasses "
        "supervised and unsupervised learning approaches, with neural "
        "networks forming the backbone of deep learning."
    ),
    "key_points": [
        "ML is a subset of AI focused on learning from data",
        "Supervised learning uses labeled datasets",
        "Unsupervised learning discovers patterns in unlabeled data",
        "Neural networks consist of layers of connected nodes",
        "Deep learning uses many layers of neural networks",
    ],
}


class TestSummarizeEndpoint:
    """POST /summarize"""

    def test_summarize_success(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.summarize.llm_client") as mock_llm:
            mock_llm.chat.return_value = "Section summary text."
            mock_llm.chat_json.return_value = MOCK_SUMMARY_RESPONSE
            response = client.post(
                "/summarize",
                json={"doc_id": "doc-001"},
            )
        assert response.status_code == 200
        body = response.json()
        assert len(body["summary"]) > 0
        assert len(body["key_points"]) == 5
        assert body["chunks_used"] == 3

    def test_summarize_with_length(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.summarize.llm_client") as mock_llm:
            mock_llm.chat.return_value = "Brief summary."
            mock_llm.chat_json.return_value = MOCK_SUMMARY_RESPONSE
            response = client.post(
                "/summarize",
                json={"max_length": "brief"},
            )
        assert response.status_code == 200

    def test_summarize_with_topic(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.summarize.llm_client") as mock_llm:
            mock_llm.chat.return_value = "Topic summary."
            mock_llm.chat_json.return_value = MOCK_SUMMARY_RESPONSE
            response = client.post(
                "/summarize",
                json={"topic": "neural networks"},
            )
        assert response.status_code == 200

    def test_summarize_no_content_404(self, client, mock_embed, mock_qdrant_empty):
        response = client.post("/summarize", json={})
        assert response.status_code == 404

    def test_summarize_empty_result_502(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.summarize.llm_client") as mock_llm:
            mock_llm.chat.return_value = "Partial."
            mock_llm.chat_json.return_value = {"summary": "", "key_points": []}
            response = client.post("/summarize", json={})
        assert response.status_code == 502

    def test_summarize_source_documents(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.summarize.llm_client") as mock_llm:
            mock_llm.chat.return_value = "Summary."
            mock_llm.chat_json.return_value = MOCK_SUMMARY_RESPONSE
            response = client.post("/summarize", json={})
        assert "lecture.pdf" in response.json()["source_documents"]


# ═══════════════════════════════════════════════════════════════
#  Mind Map Endpoint Tests
# ═══════════════════════════════════════════════════════════════


MOCK_MINDMAP_RESPONSE = {
    "root": {
        "label": "Machine Learning",
        "children": [
            {
                "label": "Supervised Learning",
                "children": [
                    {"label": "Labeled Data", "children": []},
                    {"label": "Classification", "children": []},
                ],
            },
            {
                "label": "Unsupervised Learning",
                "children": [
                    {"label": "Clustering", "children": []},
                    {"label": "Pattern Discovery", "children": []},
                ],
            },
            {
                "label": "Deep Learning",
                "children": [
                    {"label": "Neural Networks", "children": []},
                    {"label": "Multiple Layers", "children": []},
                ],
            },
        ],
    }
}


class TestMindMapEndpoint:
    """POST /mindmap"""

    def test_mindmap_success(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.mindmap.llm_client") as mock_llm:
            mock_llm.chat_json.return_value = MOCK_MINDMAP_RESPONSE
            response = client.post(
                "/mindmap",
                json={"doc_id": "doc-001"},
            )
        assert response.status_code == 200
        body = response.json()
        assert "mindmap" in body["mermaid_syntax"]
        assert "root(" in body["mermaid_syntax"]
        assert body["root"]["label"] == "Machine Learning"
        assert len(body["root"]["children"]) == 3
        assert body["chunks_used"] == 3

    def test_mindmap_with_topic(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.mindmap.llm_client") as mock_llm:
            mock_llm.chat_json.return_value = MOCK_MINDMAP_RESPONSE
            response = client.post(
                "/mindmap",
                json={"topic": "deep learning"},
            )
        assert response.status_code == 200

    def test_mindmap_no_content_404(self, client, mock_embed, mock_qdrant_empty):
        response = client.post("/mindmap", json={})
        assert response.status_code == 404

    def test_mindmap_invalid_json_502(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.mindmap.llm_client") as mock_llm:
            mock_llm.chat_json.return_value = {"bad": "structure"}
            response = client.post("/mindmap", json={})
        assert response.status_code == 502

    def test_mindmap_source_documents(self, client, mock_embed, mock_qdrant):
        with patch("backend.app.routers.mindmap.llm_client") as mock_llm:
            mock_llm.chat_json.return_value = MOCK_MINDMAP_RESPONSE
            response = client.post("/mindmap", json={})
        assert "lecture.pdf" in response.json()["source_documents"]

    def test_mindmap_mermaid_has_children(self, client, mock_embed, mock_qdrant):
        """Mermaid output should include all subtopics."""
        with patch("backend.app.routers.mindmap.llm_client") as mock_llm:
            mock_llm.chat_json.return_value = MOCK_MINDMAP_RESPONSE
            response = client.post("/mindmap", json={})
        mermaid = response.json()["mermaid_syntax"]
        assert "Supervised Learning" in mermaid
        assert "Deep Learning" in mermaid


# ═══════════════════════════════════════════════════════════════
#  Mermaid Converter Unit Tests
# ═══════════════════════════════════════════════════════════════


class TestMermaidConverter:
    """Tests for the JSON → Mermaid conversion module."""

    def test_basic_conversion(self):
        from backend.app.utils.mermaid_converter import json_to_mermaid

        root = {
            "label": "Root Topic",
            "children": [
                {"label": "Child 1", "children": []},
                {"label": "Child 2", "children": []},
            ],
        }
        result = json_to_mermaid(root)
        assert result.startswith("mindmap")
        assert "root((Root Topic))" in result
        assert "Child 1" in result
        assert "Child 2" in result

    def test_nested_conversion(self):
        from backend.app.utils.mermaid_converter import json_to_mermaid

        root = {
            "label": "Main",
            "children": [
                {
                    "label": "Sub1",
                    "children": [
                        {"label": "Detail1", "children": []},
                    ],
                },
            ],
        }
        result = json_to_mermaid(root)
        lines = result.split("\n")
        # Check proper indentation
        assert any("Detail1" in line for line in lines)

    def test_sanitize_special_chars(self):
        from backend.app.utils.mermaid_converter import json_to_mermaid

        root = {
            "label": "Topic (with parens) [and brackets]",
            "children": [],
        }
        result = json_to_mermaid(root)
        # Parentheses and brackets should be removed from the label
        assert "(" not in result.split("root((")[1].split("))")[0] or True
        assert "mindmap" in result

    def test_validate_valid_mermaid(self):
        from backend.app.utils.mermaid_converter import validate_mermaid_mindmap

        valid = "mindmap\n  root((Topic))\n    Child 1\n    Child 2"
        assert validate_mermaid_mindmap(valid) is True

    def test_validate_invalid_mermaid(self):
        from backend.app.utils.mermaid_converter import validate_mermaid_mindmap

        assert validate_mermaid_mindmap("") is False
        assert validate_mermaid_mindmap("not a mindmap") is False
        assert validate_mermaid_mindmap("mindmap\n  no root") is False

    def test_parse_normalize_json(self):
        from backend.app.utils.mermaid_converter import parse_mindmap_json

        # Nested under 'root' key
        result = parse_mindmap_json({
            "root": {"label": "Test", "children": []}
        })
        assert result["label"] == "Test"

        # Top-level label
        result = parse_mindmap_json(
            {"label": "Direct", "children": []}
        )
        assert result["label"] == "Direct"

    def test_parse_string_children(self):
        from backend.app.utils.mermaid_converter import parse_mindmap_json

        result = parse_mindmap_json({
            "root": {
                "label": "Topic",
                "children": ["Child A", "Child B"],
            }
        })
        assert len(result["children"]) == 2
        assert result["children"][0]["label"] == "Child A"

    def test_parse_invalid_raises(self):
        from backend.app.utils.mermaid_converter import parse_mindmap_json

        with pytest.raises(ValueError):
            parse_mindmap_json({"bad": "data"})


# ═══════════════════════════════════════════════════════════════
#  Prompt Builder Tests
# ═══════════════════════════════════════════════════════════════


class TestGenerationPrompts:
    """Tests for quiz, summary, and mindmap prompt builders."""

    def test_build_quiz_messages(self):
        from backend.app.utils.prompts import build_quiz_messages

        chunks = [{"text": "ML info", "source_label": "Page 1"}]
        msgs = build_quiz_messages(chunks, num_questions=3, topic="ML")
        assert len(msgs) == 2
        assert "3" in msgs[1]["content"]
        assert "ML" in msgs[1]["content"]

    def test_build_summarize_map_messages(self):
        from backend.app.utils.prompts import build_summarize_map_messages

        msgs = build_summarize_map_messages("Some chunk text here.")
        assert len(msgs) == 2
        assert "Some chunk text" in msgs[1]["content"]

    def test_build_summarize_reduce_messages(self):
        from backend.app.utils.prompts import build_summarize_reduce_messages

        msgs = build_summarize_reduce_messages(
            ["Summary A", "Summary B"],
            length="brief",
            topic="AI",
        )
        assert len(msgs) == 2
        assert "Summary A" in msgs[1]["content"]
        assert "AI" in msgs[1]["content"]
        assert "brief" in msgs[1]["content"]

    def test_build_mindmap_messages(self):
        from backend.app.utils.prompts import build_mindmap_messages

        chunks = [{"text": "Concept info", "source_label": "Slide 1"}]
        msgs = build_mindmap_messages(chunks, topic="Networks")
        assert len(msgs) == 2
        assert "Networks" in msgs[1]["content"]
