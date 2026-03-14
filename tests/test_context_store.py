"""Tests for native hybrid context retrieval."""

from __future__ import annotations

from jarvis.context_store import ContextStore
from jarvis.database import Database


def _seed_kb_document(db: Database) -> int:
    document_id = db.upsert_document(
        markdown_path="vault/sources/web/example.md",
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


def test_context_store_indexes_memory_and_kb(tmp_path) -> None:
    db = Database(str(tmp_path / "test.db"))
    store = ContextStore(db)

    memory_id = db.create_memory_entry(
        memory_key="mem-1",
        title="Tocqueville note",
        content="Civil associations prevent democratic erosion.",
        markdown_path=str(tmp_path / "vault" / "memories" / "mem-1.md"),
        memory_type="fact",
    )
    _seed_kb_document(db)

    store.index_memory(memory_id, "Tocqueville note", "Civil associations prevent erosion.")
    store.backfill_missing_embeddings()

    results = store.search("civil associations democracy", limit=5)
    assert results
    assert any(result.entry_type == "memory" for result in results)
    assert any(result.entry_type == "kb_chunk" for result in results)


def test_context_store_lexical_fallback_without_query_embeddings(tmp_path) -> None:
    db = Database(str(tmp_path / "test.db"))
    store = ContextStore(db)

    db.create_memory_entry(
        memory_key="mem-2",
        title="Federalism preference",
        content="I prefer federalism examples when discussing institutions.",
        markdown_path=str(tmp_path / "vault" / "memories" / "mem-2.md"),
        memory_type="preference",
    )

    results = store.search("federalism", limit=3)
    assert results
    assert results[0].entry_type == "memory"
