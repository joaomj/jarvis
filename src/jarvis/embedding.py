"""Semantic search with sentence-transformers embeddings.

Provides embedding generation and similarity search for context chunks.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from jarvis.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class EmbeddedChunk:
    """A chunk with its embedding vector."""

    chunk_id: int
    chunk_text: str
    embedding: list[float]
    document_id: int
    source_type: str | None = None


class EmbeddingGenerator:
    """Generate embeddings using sentence-transformers."""

    _model = None
    _model_name: str | None = None

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize embedding generator with specified model.

        Args:
            model_name: sentence-transformers model name. Default is all-MiniLM-L6-v2
                       (384 dimensions, fast, good quality).
        """
        self.model_name = model_name
        self._embedding_dim: int | None = None

    def _get_model(self):
        """Lazy-load the sentence-transformers model."""
        if EmbeddingGenerator._model is None or EmbeddingGenerator._model_name != self.model_name:
            try:
                from sentence_transformers import SentenceTransformer  # noqa: PLC0415

                logger.info("loading_embedding_model", model=self.model_name)
                EmbeddingGenerator._model = SentenceTransformer(self.model_name)
                EmbeddingGenerator._model_name = self.model_name
                self._embedding_dim = EmbeddingGenerator._model.get_sentence_embedding_dimension()
                logger.info(
                    "embedding_model_loaded",
                    model=self.model_name,
                    dimensions=self._embedding_dim,
                )
            except ImportError as err:
                logger.error("sentence_transformers_not_installed")
                msg = "sentence-transformers not installed. Run: pip install sentence-transformers"
                raise RuntimeError(msg) from err
        return EmbeddingGenerator._model

    def get_embedding_dim(self) -> int:
        """Return embedding dimension."""
        if self._embedding_dim is None:
            model = self._get_model()
            dim = model.get_sentence_embedding_dimension()
            if dim is None:
                return 0
            self._embedding_dim = dim
        return self._embedding_dim

    def embed_texts(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of text strings to embed
            batch_size: Batch size for encoding

        Returns:
            List of embedding vectors (each is a list of floats)
        """
        if not texts:
            return []

        model = self._get_model()
        logger.debug("embedding_texts", count=len(texts))

        # Encode returns numpy array, convert to list
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        return [emb.tolist() for emb in embeddings]

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a query string.

        Args:
            query: Query text

        Returns:
            Embedding vector
        """
        embeddings = self.embed_texts([query])
        return embeddings[0] if embeddings else []


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    v1 = np.array(vec1)
    v2 = np.array(vec2)

    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(np.dot(v1, v2) / (norm1 * norm2))
