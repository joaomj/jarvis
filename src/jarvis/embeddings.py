"""Embedding helpers for semantic context retrieval."""

from __future__ import annotations

import hashlib
import math
import os
from functools import lru_cache
from typing import Any

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency at import time
    SentenceTransformer = None  # type: ignore[assignment,misc]

from jarvis.logging_config import get_logger

logger = get_logger(__name__)

EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
EMBEDDING_DIMENSIONS = 1024


@lru_cache(maxsize=1)
def _load_model() -> Any | None:
    """Load BGE-M3 once and cache model instance.

    Returns None when local model load fails; callers fall back to deterministic
    hashed embeddings so tests and offline environments continue working.
    """
    try:
        if SentenceTransformer is None:
            raise RuntimeError("sentence-transformers is not available")
        allow_download = os.getenv("JARVIS_EMBEDDINGS_DOWNLOAD", "1") == "1"
        model = SentenceTransformer(EMBEDDING_MODEL_NAME, local_files_only=not allow_download)
        logger.info("embedding_model_loaded", model=EMBEDDING_MODEL_NAME)
        return model
    except Exception as error:  # pragma: no cover - environment dependent
        logger.warning(
            "embedding_model_load_failed",
            model=EMBEDDING_MODEL_NAME,
            error=str(error),
        )
        return None


def embed_text(text: str) -> list[float]:
    """Embed one text using BGE-M3, with deterministic fallback."""
    normalized = text.strip()
    if not normalized:
        raise ValueError("text for embedding cannot be empty")

    model = _load_model()
    if model is None:
        return _fallback_embedding(normalized)

    vector = model.encode(normalized, normalize_embeddings=True)
    return [float(value) for value in vector.tolist()]


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts preserving input order for non-empty texts."""
    normalized = [text.strip() for text in texts if text.strip()]
    if not normalized:
        return []

    model = _load_model()
    if model is None:
        return [_fallback_embedding(item) for item in normalized]

    vectors = model.encode(normalized, normalize_embeddings=True)
    return [[float(value) for value in vector.tolist()] for vector in vectors]


def _fallback_embedding(text: str) -> list[float]:
    """Create deterministic unit vector when model is unavailable."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    seed = digest
    while len(values) < EMBEDDING_DIMENSIONS:
        for index in range(0, len(seed), 2):
            if len(values) >= EMBEDDING_DIMENSIONS:
                break
            chunk = seed[index : index + 2]
            number = int.from_bytes(chunk, byteorder="big", signed=False)
            values.append((number / 32767.5) - 1.0)
        seed = hashlib.sha256(seed).digest()

    norm = math.sqrt(sum(item * item for item in values))
    if norm == 0:
        return [0.0] * EMBEDDING_DIMENSIONS
    return [item / norm for item in values]
