"""
Text/Markdown parser — handles plain text and markdown files.

Splits text into paragraph-level sections.  For short files (< 5 paragraphs),
returns a single section to avoid over-fragmentation.
"""

import logging
import re
from typing import List

from spark.parsers.base import BaseParser, ParsedSection

logger = logging.getLogger(__name__)

# Minimum number of paragraphs to split into separate sections
_MIN_PARAGRAPHS_TO_SPLIT = 5


class TextParser(BaseParser):
    """Parse plain text and markdown files into sections."""

    def parse(self, file_bytes: bytes, filename: str) -> List[ParsedSection]:
        """
        Parse a text/markdown file from raw bytes.

        Args:
            file_bytes: Raw file content.
            filename: Original filename for logging.

        Returns:
            List of ParsedSection objects.

        Raises:
            ValueError: If the file is empty or cannot be decoded.
        """
        # ── Decode ─────────────────────────────────────────────
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = file_bytes.decode("latin-1")
            except Exception as exc:
                raise ValueError(
                    f"Cannot decode '{filename}': {exc}"
                ) from exc

        text = text.strip()
        if not text:
            raise ValueError(f"File '{filename}' is empty.")

        # ── Split into paragraphs ──────────────────────────────
        # Split on 2+ newlines (paragraph boundaries)
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

        # For short documents, return a single section
        if len(paragraphs) < _MIN_PARAGRAPHS_TO_SPLIT:
            return [
                ParsedSection(
                    label="Full Document",
                    index=0,
                    text=text,
                    metadata={"paragraph_count": len(paragraphs)},
                )
            ]

        # For longer documents, group paragraphs into sections
        sections: List[ParsedSection] = []
        for idx, para in enumerate(paragraphs):
            sections.append(
                ParsedSection(
                    label=f"Section {idx + 1}",
                    index=idx,
                    text=para,
                    metadata={"paragraph_index": idx},
                )
            )

        logger.info(
            "Parsed '%s': %d paragraphs → %d sections.",
            filename,
            len(paragraphs),
            len(sections),
        )
        return sections
