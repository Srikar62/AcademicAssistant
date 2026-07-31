"""
Embedding service for the API layer.

Wraps sentence-transformers to embed user queries for vector search.
The model is loaded once and cached for the lifetime of the process.
"""

import logging
from typing import List

import numpy as np

from backend.app.config import settings

logger = logging.getLogger(__name__)

# ─── Module-level model cache ─────────────────────────────────
_model = None


def _get_model():
    """Lazy-load the embedding model."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model '%s' …", settings.EMBEDDING_MODEL)
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Embedding model loaded.")
    return _model


def embed_query(query: str) -> List[float]:
    """
    Embed a single query string.

    Args:
        query: The user's question or search text.

    Returns:
        List of floats (the embedding vector).
    """
    model = _get_model()
    embedding = model.encode(
        query,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embedding.tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Embed a batch of text strings.

    Args:
        texts: List of strings to embed.

    Returns:
        List of embedding vectors.
    """
    if not texts:
        return []
    model = _get_model()
    embeddings = model.encode(
        texts,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return [emb.tolist() for emb in embeddings]
