"""
Sentence-aware text chunker.

Splits text into chunks of approximately `max_tokens` tokens with
configurable overlap.  Uses NLTK's sentence tokenizer for boundary
detection so chunks never break mid-sentence.

PPTX-specific logic: slides are treated as natural boundaries — short
slides are merged together rather than left as tiny fragments.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

import nltk
import tiktoken

# Download the sentence tokenizer data (no-op if already present)
try:
    nltk.data.find("tokenizers/punkt_tab")
except LookupError:
    nltk.download("punkt_tab", quiet=True)

from nltk.tokenize import sent_tokenize

from spark.parsers.base import ParsedSection

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A single chunk of text ready for embedding."""
    chunk_index: int
    text: str
    token_count: int
    source_label: str          # e.g. "Page 3", "Slide 7"
    source_indices: List[int]  # which sections contributed to this chunk
    metadata: dict = field(default_factory=dict)


def _estimate_tokens(text: str) -> int:
    """
    Accurate token count using tiktoken's cl100k_base encoding.
    Works correctly for CJK, multilingual, and code content.
    The encoding is cached at module level — no per-call overhead.
    """
    return len(_TIKTOKEN_ENC.encode(text, disallowed_special=()))


# Module-level tiktoken encoding (loaded once, reused across calls)
_TIKTOKEN_ENC = tiktoken.get_encoding("cl100k_base")


def chunk_sections(
    sections: List[ParsedSection],
    max_tokens: int = 400,
    overlap_fraction: float = 0.15,
) -> List[Chunk]:
    """
    Chunk a list of parsed sections into embedding-ready text chunks.

    Args:
        sections: Output from a parser (list of ParsedSection).
        max_tokens: Target maximum tokens per chunk.
        overlap_fraction: Fraction of `max_tokens` to overlap between chunks.

    Returns:
        List of Chunk objects.
    """
    # Flatten all sections into sentences, tracking their source
    all_sentences: List[dict] = []
    for section in sections:
        sentences = sent_tokenize(section.text)
        for sent in sentences:
            sent = sent.strip()
            if sent:
                all_sentences.append({
                    "text": sent,
                    "tokens": _estimate_tokens(sent),
                    "source_label": section.label,
                    "source_index": section.index,
                    "metadata": section.metadata,
                })

    if not all_sentences:
        return []

    overlap_tokens = int(max_tokens * overlap_fraction)
    chunks: List[Chunk] = []
    chunk_idx = 0
    i = 0  # current sentence index

    while i < len(all_sentences):
        current_chunk_sents: List[dict] = []
        current_tokens = 0

        # ── Fill the chunk up to max_tokens ────────────────────
        j = i
        while j < len(all_sentences):
            sent = all_sentences[j]
            # Always include at least one sentence per chunk
            if current_tokens + sent["tokens"] > max_tokens and current_chunk_sents:
                break
            current_chunk_sents.append(sent)
            current_tokens += sent["tokens"]
            j += 1

        # ── Build the chunk ────────────────────────────────────
        chunk_text = " ".join(s["text"] for s in current_chunk_sents)
        source_labels = list(dict.fromkeys(
            s["source_label"] for s in current_chunk_sents
        ))
        source_indices = list(dict.fromkeys(
            s["source_index"] for s in current_chunk_sents
        ))

        # Merge metadata from all contributing sections
        merged_metadata = {}
        for s in current_chunk_sents:
            merged_metadata.update(s["metadata"])

        chunks.append(Chunk(
            chunk_index=chunk_idx,
            text=chunk_text,
            token_count=_estimate_tokens(chunk_text),
            source_label=", ".join(source_labels),
            source_indices=source_indices,
            metadata=merged_metadata,
        ))
        chunk_idx += 1

        # ── Advance with overlap ───────────────────────────────
        # Walk backward from the end of the current chunk to find
        # the overlap start point
        if j >= len(all_sentences):
            break  # We've consumed everything

        overlap_count = 0
        overlap_start = j
        for k in range(j - 1, i - 1, -1):
            overlap_count += all_sentences[k]["tokens"]
            if overlap_count >= overlap_tokens:
                overlap_start = k
                break

        i = overlap_start if overlap_start > i else j

    logger.info(
        "Chunked %d sections (%d sentences) → %d chunks.",
        len(sections),
        len(all_sentences),
        len(chunks),
    )
    return chunks


def chunk_pptx_sections(
    sections: List[ParsedSection],
    max_tokens: int = 400,
    overlap_fraction: float = 0.15,
    min_slide_tokens: int = 50,
) -> List[Chunk]:
    """
    PPTX-specific chunking: treat each slide as a natural boundary.
    Short slides (< min_slide_tokens) are merged with the next slide
    before the standard chunking pass.

    Args:
        sections: Parsed slides from PPTXParser.
        max_tokens: Target maximum tokens per chunk.
        overlap_fraction: Overlap fraction.
        min_slide_tokens: Slides shorter than this are merged.

    Returns:
        List of Chunk objects.
    """
    if not sections:
        return []

    # ── Merge short slides ─────────────────────────────────────
    merged_sections: List[ParsedSection] = []
    buffer: Optional[ParsedSection] = None

    for section in sections:
        tokens = _estimate_tokens(section.text)

        if buffer is None:
            if tokens < min_slide_tokens:
                buffer = section
            else:
                merged_sections.append(section)
        else:
            # Merge buffer with current section
            combined_text = buffer.text + "\n\n" + section.text
            merged = ParsedSection(
                label=f"{buffer.label}–{section.label}",
                index=buffer.index,
                text=combined_text,
                metadata={**buffer.metadata, **section.metadata},
            )
            if _estimate_tokens(combined_text) < min_slide_tokens:
                buffer = merged  # keep merging
            else:
                merged_sections.append(merged)
                buffer = None

    if buffer is not None:
        merged_sections.append(buffer)

    # ── Apply standard chunking to merged sections ─────────────
    return chunk_sections(
        merged_sections,
        max_tokens=max_tokens,
        overlap_fraction=overlap_fraction,
    )
