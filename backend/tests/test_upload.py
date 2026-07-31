"""
Tests for the upload endpoint and related document status polling.

All infrastructure services (MinIO, Kafka) are mocked so these tests
run without Docker.
"""

import io

from backend.app.services.document_service import document_service


# ═══════════════════════════════════════════════════════════════
#  Upload Endpoint Tests
# ═══════════════════════════════════════════════════════════════


class TestUploadEndpoint:
    """POST /upload"""

    def test_upload_pdf_success(self, client, mock_minio, mock_kafka):
        """A valid PDF upload should return 201 with a doc_id."""
        response = client.post(
            "/upload",
            files={"file": ("lecture.pdf", b"%PDF-1.4 fake content", "application/pdf")},
            data={"student_id": "stu-001", "course_id": "cs-101"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["filename"] == "lecture.pdf"
        assert body["file_type"] == ".pdf"
        assert body["status"] == "uploaded"
        assert "doc_id" in body

        # MinIO should have been called
        mock_minio.upload_file.assert_called_once()
        # Kafka should have been called
        mock_kafka.publish.assert_called_once()

    def test_upload_pptx_success(self, client, mock_minio, mock_kafka):
        """PPTX files should also be accepted."""
        response = client.post(
            "/upload",
            files={"file": ("slides.pptx", b"PK\x03\x04 fake pptx", "application/octet-stream")},
        )
        assert response.status_code == 201
        assert response.json()["file_type"] == ".pptx"

    def test_upload_txt_success(self, client, mock_minio, mock_kafka):
        """Plain text notes should be accepted."""
        response = client.post(
            "/upload",
            files={"file": ("notes.txt", b"Chapter 1: Introduction", "text/plain")},
        )
        assert response.status_code == 201
        assert response.json()["file_type"] == ".txt"

    def test_upload_md_success(self, client, mock_minio, mock_kafka):
        """Markdown files should be accepted."""
        response = client.post(
            "/upload",
            files={"file": ("notes.md", b"# Heading\nSome notes", "text/plain")},
        )
        assert response.status_code == 201
        assert response.json()["file_type"] == ".md"

    def test_upload_unsupported_file_type(self, client, mock_minio, mock_kafka):
        """A .exe file should be rejected with 400."""
        response = client.post(
            "/upload",
            files={"file": ("malware.exe", b"MZ bad stuff", "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "Unsupported file type" in response.json()["detail"]

    def test_upload_no_filename(self, client, mock_minio, mock_kafka):
        """A file with no name should be rejected (400 or 422)."""
        response = client.post(
            "/upload",
            files={"file": ("", b"some bytes", "application/octet-stream")},
        )
        assert response.status_code in (400, 422)

    def test_upload_kafka_failure_still_succeeds(self, client, mock_minio, mock_kafka):
        """
        If Kafka is unreachable the upload should still succeed
        (file is safely in MinIO).
        """
        mock_kafka.publish.return_value = False

        response = client.post(
            "/upload",
            files={"file": ("lecture.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        # Still 201 — file is persisted
        assert response.status_code == 201

    def test_upload_minio_failure_returns_502(self, client, mock_minio, mock_kafka):
        """If MinIO is unreachable the upload should fail with 502."""
        mock_minio.upload_file.side_effect = Exception("Connection refused")

        response = client.post(
            "/upload",
            files={"file": ("lecture.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert response.status_code == 502

    def test_upload_creates_document_record(self, client, mock_minio, mock_kafka):
        """The in-memory document store should have the new document."""
        response = client.post(
            "/upload",
            files={"file": ("lecture.pdf", b"%PDF-1.4 fake", "application/pdf")},
            data={"student_id": "stu-001", "course_id": "cs-101"},
        )
        doc_id = response.json()["doc_id"]
        doc = document_service.get(doc_id)
        assert doc is not None
        assert doc.student_id == "stu-001"
        assert doc.course_id == "cs-101"


# ═══════════════════════════════════════════════════════════════
#  Document Status Endpoint Tests
# ═══════════════════════════════════════════════════════════════


class TestDocumentStatusEndpoint:
    """GET /documents/{doc_id}/status"""

    def test_status_after_upload(self, client, mock_minio, mock_kafka):
        """After upload, status should be 'uploaded'."""
        upload_resp = client.post(
            "/upload",
            files={"file": ("lecture.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        doc_id = upload_resp.json()["doc_id"]

        status_resp = client.get(f"/documents/{doc_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "uploaded"

    def test_status_not_found(self, client):
        """Querying a non-existent doc should return 404."""
        response = client.get("/documents/nonexistent-id/status")
        assert response.status_code == 404

    def test_list_documents(self, client, mock_minio, mock_kafka):
        """Listing should include all uploaded documents."""
        # Upload two files
        client.post(
            "/upload",
            files={"file": ("a.pdf", b"%PDF-1.4", "application/pdf")},
        )
        client.post(
            "/upload",
            files={"file": ("b.txt", b"hello", "text/plain")},
        )

        response = client.get("/documents")
        assert response.status_code == 200
        docs = response.json()
        assert len(docs) == 2


# ═══════════════════════════════════════════════════════════════
#  Health Endpoint Tests
# ═══════════════════════════════════════════════════════════════


class TestHealthEndpoints:
    """GET / and GET /health"""

    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "running"

    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ═══════════════════════════════════════════════════════════════
#  Magic Byte Validation Tests
# ═══════════════════════════════════════════════════════════════


class TestMagicByteValidation:
    """Verify that file content is validated against magic byte signatures."""

    def test_upload_pdf_with_wrong_magic_bytes(self, client, mock_minio, mock_kafka):
        """A .pdf file containing ZIP bytes should be rejected."""
        response = client.post(
            "/upload",
            files={"file": ("lecture.pdf", b"PK\x03\x04 this is ZIP", "application/pdf")},
        )
        assert response.status_code == 400
        assert "does not match" in response.json()["detail"]

    def test_upload_pptx_with_wrong_magic_bytes(self, client, mock_minio, mock_kafka):
        """A .pptx file containing PDF bytes should be rejected."""
        response = client.post(
            "/upload",
            files={"file": ("slides.pptx", b"%PDF-1.4 this is PDF", "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "does not match" in response.json()["detail"]

    def test_upload_txt_with_binary_content(self, client, mock_minio, mock_kafka):
        """A .txt file starting with a PE header (MZ) should be rejected."""
        response = client.post(
            "/upload",
            files={"file": ("notes.txt", b"MZ\x90\x00 binary content", "text/plain")},
        )
        assert response.status_code == 400
        assert "binary" in response.json()["detail"]

    def test_upload_txt_with_pdf_content(self, client, mock_minio, mock_kafka):
        """A .txt file starting with PDF magic bytes should be rejected."""
        response = client.post(
            "/upload",
            files={"file": ("notes.txt", b"%PDF-1.4 disguised", "text/plain")},
        )
        assert response.status_code == 400
        assert "binary" in response.json()["detail"]

    def test_upload_pdf_with_valid_magic_bytes(self, client, mock_minio, mock_kafka):
        """A .pdf with proper %PDF prefix should pass validation."""
        response = client.post(
            "/upload",
            files={"file": ("lecture.pdf", b"%PDF-1.4 valid content", "application/pdf")},
        )
        assert response.status_code == 201

    def test_upload_pptx_with_valid_magic_bytes(self, client, mock_minio, mock_kafka):
        """A .pptx with proper PK prefix should pass validation."""
        response = client.post(
            "/upload",
            files={"file": ("slides.pptx", b"PK\x03\x04 valid pptx", "application/octet-stream")},
        )
        assert response.status_code == 201

    def test_upload_md_with_non_utf8_content(self, client, mock_minio, mock_kafka):
        """A .md file with non-UTF-8 bytes should be rejected."""
        # 0xfe 0xff are invalid UTF-8 start bytes
        response = client.post(
            "/upload",
            files={"file": ("notes.md", b"\xfe\xff\x00\x01 invalid", "text/plain")},
        )
        assert response.status_code == 400
        assert "UTF-8" in response.json()["detail"]

    def test_upload_txt_with_valid_utf8(self, client, mock_minio, mock_kafka):
        """Valid UTF-8 text files should pass magic byte validation."""
        response = client.post(
            "/upload",
            files={"file": ("notes.txt", "Hello, 世界! 🌍".encode("utf-8"), "text/plain")},
        )
        assert response.status_code == 201

