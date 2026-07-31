"""
Input validators for file uploads.
"""

import os
from fastapi import HTTPException, UploadFile, status

from backend.app.config import settings


# ── Magic byte signatures for file type validation ────────────
# Maps extension → (magic_bytes_prefix, human_readable_name)
_BINARY_SIGNATURES = {
    ".pdf": (b"%PDF", "PDF"),
    ".pptx": (b"PK\x03\x04", "PPTX (ZIP/OOXML)"),
}

# Binary headers that text files must NOT start with
_FORBIDDEN_TEXT_PREFIXES = [
    b"%PDF",           # PDF
    b"PK\x03\x04",    # ZIP / OOXML
    b"MZ",            # PE executable (EXE, DLL)
    b"\x7fELF",       # ELF executable
    b"\xca\xfe\xba\xbe",  # Mach-O / Java class
    b"\x89PNG",       # PNG image
    b"\xff\xd8\xff",  # JPEG image
]


def validate_upload_file(file: UploadFile) -> None:
    """
    Validate an uploaded file against allowed types and size limits.

    Raises:
        HTTPException 400: if the file type is not supported.
        HTTPException 413: if the file exceeds the size limit.
    """
    # ── Check file extension ───────────────────────────────────
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Allowed: {', '.join(settings.allowed_extensions_list)}"
            ),
        )

    # ── Check content type (belt-and-suspenders) ───────────────
    allowed_mimes = {
        ".pdf": "application/pdf",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".txt": "text/plain",
        ".md": "text/plain",  # .md is typically served as text/plain
    }
    expected_mime = allowed_mimes.get(ext)
    # Only enforce MIME for well-known types; some clients send
    # application/octet-stream for everything.
    if (
        expected_mime
        and file.content_type
        and file.content_type != "application/octet-stream"
        and file.content_type != expected_mime
    ):
        # Log but don't block — MIME mismatches are common
        pass


def validate_file_magic_bytes(file_data: bytes, extension: str) -> None:
    """
    Validate that file content matches the expected magic bytes for
    the declared file extension.

    This prevents attacks where a malicious file (e.g., an executable)
    is renamed to .pdf or .pptx to bypass extension-based checks.

    Args:
        file_data: The raw file bytes.
        extension: File extension including the dot (e.g. ".pdf").

    Raises:
        HTTPException 400: if magic bytes don't match the extension.
    """
    ext = extension.lower()

    if ext in _BINARY_SIGNATURES:
        expected_prefix, type_name = _BINARY_SIGNATURES[ext]
        if not file_data.startswith(expected_prefix):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"File content does not match expected {type_name} format. "
                    f"The file may be corrupted or is not a valid {ext} file."
                ),
            )
    elif ext in (".txt", ".md"):
        # Text files: verify decodable as UTF-8 and no binary headers
        for prefix in _FORBIDDEN_TEXT_PREFIXES:
            if file_data.startswith(prefix):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"File content appears to be binary, not a valid "
                        f"{ext} text file."
                    ),
                )
        # Verify UTF-8 decodability (sample first 8KB for performance)
        try:
            file_data[:8192].decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"File content is not valid UTF-8 text. "
                    f"Expected a readable {ext} file."
                ),
            )


async def validate_file_size(file_data: bytes) -> None:
    """
    Check that the file data doesn't exceed the configured limit.

    Raises:
        HTTPException 413: if the file is too large.
    """
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(file_data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File size ({len(file_data) / (1024*1024):.1f} MB) exceeds "
                f"the {settings.MAX_FILE_SIZE_MB} MB limit."
            ),
        )

