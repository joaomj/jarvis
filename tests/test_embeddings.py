"""Tests for embedding helpers."""

from __future__ import annotations

from jarvis.embeddings import EMBEDDING_DIMENSIONS, embed_batch, embed_text


def test_embed_text_returns_expected_dimensions() -> None:
    vector = embed_text("democracy and civic institutions")
    assert len(vector) == EMBEDDING_DIMENSIONS


def test_embed_batch_returns_one_vector_per_non_empty_text() -> None:
    vectors = embed_batch(["first text", "", "second text"])
    assert len(vectors) == 2
    assert all(len(vector) == EMBEDDING_DIMENSIONS for vector in vectors)
