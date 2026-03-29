"""Tests for hybrid context retrieval."""

from __future__ import annotations

from jarvis.context_store import ContextStore
from jarvis.database import Database


def _seed_kb_document(db: Database, *, path: str = "vault/sources/web/example.md") -> int:
    document_id = db.upsert_document(
        markdown_path=path,
        url_original="https://example.com/democracy",
        url_canonical="https://example.com/democracy",
        title="Democracy Notes",
        domain="example.com",
        captured_at="2026-01-01T00:00:00Z",
        content_hash="hash-democracy",
    )
    db.replace_document_chunks(
        document_id,
        [
            {
                "chunk_index": 0,
                "heading": "Risks",
                "line_start": 1,
                "line_end": 5,
                "chunk_text": "Democracy can decay into soft despotism without civic institutions.",
            }
        ],
    )
    db.upsert_fts_for_document(document_id)
    return document_id


def test_context_store_searches_kb_chunks(tmp_path) -> None:
    db = Database(str(tmp_path / "test.db"))
    store = ContextStore(db)

    _seed_kb_document(db)

    results = store.search("soft despotism", limit=5)
    assert results
    assert results[0].entry_type == "kb_chunk"
    assert "soft despotism" in results[0].snippet.lower()


def test_context_store_lexical_fallback_without_vectors(tmp_path) -> None:
    db = Database(str(tmp_path / "test.db"))
    store = ContextStore(db)

    _seed_kb_document(db)

    results = store.search("civic institutions", limit=3)
    assert results
    assert results[0].entry_type == "kb_chunk"
    assert "civic" in results[0].snippet.lower()


def test_context_store_returns_empty_for_no_match(tmp_path) -> None:
    db = Database(str(tmp_path / "test.db"))
    store = ContextStore(db)

    _seed_kb_document(db)

    results = store.search("quantum physics dark matter black holes", limit=5)
    assert results == []


def test_context_store_empty_query_returns_nothing(tmp_path) -> None:
    db = Database(str(tmp_path / "test.db"))
    store = ContextStore(db)

    results = store.search("", limit=5)
    assert results == []
    results = store.search("   ", limit=5)
    assert results == []
