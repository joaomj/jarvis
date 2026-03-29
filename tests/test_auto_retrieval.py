"""Tests for auto-retrieval engine."""

from __future__ import annotations

from jarvis.auto_retrieval import _deduplicate, retrieve_context


def test_retrieve_context_returns_empty_for_short_query(tmp_path) -> None:
    from jarvis.context_store import ContextStore
    from jarvis.database import Database

    db = Database(str(tmp_path / "test.db"))
    store = ContextStore(db)

    result = retrieve_context(store, "/dev/null", "")
    assert result.system_prefix == ""
    assert result.sources_used == 0

    result = retrieve_context(store, "/dev/null", "   ")
    assert result.system_prefix == ""


def test_retrieve_context_empty_for_no_matches(tmp_path) -> None:
    from jarvis.context_store import ContextStore
    from jarvis.database import Database

    db = Database(str(tmp_path / "test.db"))
    store = ContextStore(db)

    result = retrieve_context(store, "/dev/null", "xyznonexistent123")
    assert result.system_prefix == ""


def test_retrieve_context_finds_kb_content(tmp_path) -> None:
    from jarvis.context_store import ContextStore
    from jarvis.database import Database

    db = Database(str(tmp_path / "test.db"))
    store = ContextStore(db)

    db.upsert_document(
        markdown_path="vault/sources/web/example.md",
        url_original="https://example.com/democracy",
        url_canonical="https://example.com/democracy",
        title="Democracy Notes",
        domain="example.com",
        captured_at="2026-01-01T00:00:00Z",
        content_hash="hash-democracy",
    )
    db.replace_document_chunks(
        1,
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
    db.upsert_fts_for_document(1)

    result = retrieve_context(store, "/dev/null", "soft despotism democracy")
    assert result.sources_used >= 1
    assert "soft despotism" in result.system_prefix


def test_deduplicate_removes_similar_snippets() -> None:
    snippets = [
        ("Democracy can decay into soft despotism", "source1", 0.9),
        ("democracy can decay into soft despotism", "source2", 0.8),
        ("Completely different topic about economics", "source3", 0.7),
    ]
    result = _deduplicate(snippets)
    assert len(result) == 2
    assert result[0][0] == snippets[0][0]
    assert result[1][0] == snippets[2][0]


def test_retrieve_context_respects_max_chars(tmp_path) -> None:
    from jarvis.context_store import ContextStore
    from jarvis.database import Database

    db = Database(str(tmp_path / "test.db"))
    store = ContextStore(db)

    for i in range(10):
        db.upsert_document(
            markdown_path=f"vault/sources/web/doc{i}.md",
            url_original=f"https://example.com/doc{i}",
            url_canonical=f"https://example.com/doc{i}",
            title=f"Document {i}",
            domain="example.com",
            captured_at="2026-01-01T00:00:00Z",
            content_hash=f"hash-{i}",
        )
        db.replace_document_chunks(
            i + 1,
            [
                {
                    "chunk_index": 0,
                    "heading": None,
                    "line_start": 1,
                    "line_end": 1,
                    "chunk_text": f"Unique content about topic {i} that is fairly long.",
                }
            ],
        )
        db.upsert_fts_for_document(i + 1)

    result = retrieve_context(store, "/dev/null", "topic", max_chars=200)
    assert result.sources_used >= 1
    assert len(result.system_prefix) <= 300
