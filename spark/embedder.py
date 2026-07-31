"""
Embedding service — wraps sentence-transformers for use in Spark's mapInPandas.

The key design choice: the model is loaded ONCE per executor partition
(via a module-level cache keyed by model name), so we don't pay the
model-loading cost per row.  This is the primary reason for using
mapInPandas instead of a regular UDF.
"""

import logging
from typing import Iterator, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ─── Module-level model cache (one per executor process) ───────
_MODEL_CACHE = {}


def _get_model(model_name: str):
    """
    Load the sentence-transformers model, caching it so subsequent
    calls within the same executor process reuse it.
    """
    if model_name not in _MODEL_CACHE:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model '%s' …", model_name)
        _MODEL_CACHE[model_name] = SentenceTransformer(model_name)
        logger.info("Model '%s' loaded.", model_name)
    return _MODEL_CACHE[model_name]


def embed_texts(
    texts: List[str],
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 64,
) -> np.ndarray:
    """
    Embed a list of texts using the specified sentence-transformers model.

    Args:
        texts: List of text strings to embed.
        model_name: HuggingFace model identifier.
        batch_size: Encoding batch size.

    Returns:
        numpy array of shape (len(texts), embedding_dim).
    """
    model = _get_model(model_name)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embeddings


def embed_chunks_pandas_udf(
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 64,
):
    """
    Return a function compatible with Spark's mapInPandas.

    The returned function:
      - Receives an iterator of pandas DataFrames (each DF is a partition)
      - Expects a 'text' column
      - Yields DataFrames with an added 'embedding' column (list of floats)

    Usage in Spark:
        embed_fn = embed_chunks_pandas_udf("all-MiniLM-L6-v2")
        result_df = chunks_df.mapInPandas(embed_fn, schema=output_schema)
    """

    def _embed_partition(
        iterator: Iterator[pd.DataFrame],
    ) -> Iterator[pd.DataFrame]:
        """Process each partition: load model once, embed all rows."""
        model = _get_model(model_name)

        for pdf in iterator:
            if pdf.empty:
                # Yield empty frame with the embedding column added
                pdf["embedding"] = pd.Series(dtype=object)
                yield pdf
                continue

            texts = pdf["text"].tolist()
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )

            # Store as list-of-floats so it serializes cleanly
            pdf["embedding"] = [emb.tolist() for emb in embeddings]
            yield pdf

    return _embed_partition


def embed_chunks_batch(
    chunks_data: List[dict],
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 64,
) -> List[dict]:
    """
    Standalone batch embedding (used when running without Spark).

    Args:
        chunks_data: List of dicts, each must have a 'text' key.
        model_name: Model to use.
        batch_size: Encoding batch size.

    Returns:
        Same list of dicts with an 'embedding' key added to each.
    """
    if not chunks_data:
        return chunks_data

    texts = [c["text"] for c in chunks_data]
    embeddings = embed_texts(texts, model_name=model_name, batch_size=batch_size)

    for chunk, emb in zip(chunks_data, embeddings):
        chunk["embedding"] = emb.tolist()

    logger.info("Embedded %d chunks with '%s'.", len(chunks_data), model_name)
    return chunks_data
