"""
Base parser interface and parser dispatcher.

Each parser takes raw file bytes and returns a list of ParsedSection
objects, where each section has a label (page number, slide number, etc.)
and the extracted text.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List


@dataclass
class ParsedSection:
    """
    A single section of extracted text from a document.

    Attributes:
        label: Human-readable origin (e.g. "Page 3", "Slide 7").
        index: Numeric index of the section (0-based).
        text: The extracted text content.
        metadata: Optional extra metadata (e.g. slide title).
    """
    label: str
    index: int
    text: str
    metadata: dict = field(default_factory=dict)


class BaseParser(ABC):
    """Abstract base for all document parsers."""

    @abstractmethod
    def parse(self, file_bytes: bytes, filename: str) -> List[ParsedSection]:
        """
        Parse raw file bytes into a list of text sections.

        Args:
            file_bytes: The raw bytes of the document.
            filename: Original filename (used for logging).

        Returns:
            List of ParsedSection objects.

        Raises:
            ValueError: If the file cannot be parsed.
        """
        ...


def get_parser(file_type: str) -> BaseParser:
    """
    Return the appropriate parser for a given file extension.

    Args:
        file_type: File extension including the dot (e.g. ".pdf").

    Returns:
        An instantiated parser.

    Raises:
        ValueError: If the file type is unsupported.
    """
    # Import here to avoid circular imports and to keep the base module lightweight
    from spark.parsers.pdf_parser import PDFParser
    from spark.parsers.pptx_parser import PPTXParser
    from spark.parsers.text_parser import TextParser

    parsers = {
        ".pdf": PDFParser,
        ".pptx": PPTXParser,
        ".txt": TextParser,
        ".md": TextParser,
    }

    parser_cls = parsers.get(file_type.lower())
    if parser_cls is None:
        raise ValueError(
            f"Unsupported file type: '{file_type}'. "
            f"Supported: {list(parsers.keys())}"
        )

    return parser_cls()
