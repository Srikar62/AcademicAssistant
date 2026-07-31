"""
PDF parser — extracts text from PDF documents using PyMuPDF (fitz).

Returns one ParsedSection per page with the page number as label.
Handles corrupted PDFs gracefully by raising ValueError with details.
"""

import logging
from typing import List

import fitz  # PyMuPDF

from spark.parsers.base import BaseParser, ParsedSection

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """Extract text from PDFs page-by-page using PyMuPDF."""

    def parse(self, file_bytes: bytes, filename: str) -> List[ParsedSection]:
        """
        Parse a PDF from raw bytes.

        Args:
            file_bytes: Raw PDF content.
            filename: Original filename for logging.

        Returns:
            One ParsedSection per page with non-empty text.

        Raises:
            ValueError: If the PDF is corrupted or unreadable.
        """
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as exc:
            raise ValueError(
                f"Failed to open PDF '{filename}': {exc}"
            ) from exc

        sections: List[ParsedSection] = []

        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                text = page.get_text("text").strip()

                if not text:
                    logger.debug(
                        "Page %d of '%s' has no extractable text (scanned image?).",
                        page_num + 1,
                        filename,
                    )
                    continue

                sections.append(
                    ParsedSection(
                        label=f"Page {page_num + 1}",
                        index=page_num,
                        text=text,
                        metadata={
                            "page_number": page_num + 1,
                            "total_pages": len(doc),
                        },
                    )
                )
            except Exception as exc:
                logger.warning(
                    "Error extracting page %d of '%s': %s",
                    page_num + 1,
                    filename,
                    exc,
                )

        total_pages = len(doc)
        doc.close()

        if not sections:
            raise ValueError(
                f"PDF '{filename}' yielded no extractable text "
                f"({total_pages} pages scanned)."
            )

        logger.info(
            "Parsed '%s': %d pages, %d with text.",
            filename,
            total_pages,
            len(sections),
        )
        return sections

