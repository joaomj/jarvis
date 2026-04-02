"""Tests for markdown chunking and KB indexer behavior."""

from __future__ import annotations

import sqlite3

from jarvis.database import Database
from jarvis.kb_indexer import KBIndexer


def _write_markdown(path, title: str, body: str) -> None:
    content = (
        "---\n"
        "url: https://example.com/article\n"
        f"title: {title}\n"
        "captured_at: 2026-01-01T00:00:00Z\n"
        "---\n\n"
        f"{body}\n"
    )
    path.write_text(content, encoding="utf-8")


def test_indexer_is_idempotent_for_unchanged_files(tmp_path) -> None:
    """Re-indexing unchanged markdown does not duplicate chunk rows."""
    db = Database(str(tmp_path / "test.db"))
    content_dir = tmp_path / "vault" / "raw" / "url-saves"
    content_dir.mkdir(parents=True)

    article_path = content_dir / "a.md"
    _write_markdown(article_path, "Article A", "# Intro\nPython sqlite indexing.")

    indexer = KBIndexer(db=db, content_dir=str(content_dir), chunk_size_chars=200)

    first = indexer.index_all()
    second = indexer.index_all()

    assert first.indexed_files == 1
    assert second.indexed_files == 0
    assert second.skipped_files == 1

    docs = db.get_recent_kb_documents(limit=5)
    doc = next((item for item in docs if str(item.get("markdown_path", "")).endswith("a.md")), None)
    assert doc is not None

    with sqlite3.connect(db.db_path) as conn:
        chunk_count = conn.execute(
            "SELECT COUNT(*) FROM kb_chunks WHERE document_id = ?",
            (doc["id"],),
        ).fetchone()[0]
    assert chunk_count >= 1


def test_indexer_replaces_chunks_when_file_changes(tmp_path) -> None:
    """Changed markdown replaces old chunk set."""
    db = Database(str(tmp_path / "test.db"))
    content_dir = tmp_path / "vault" / "raw" / "url-saves"
    content_dir.mkdir(parents=True)

    article_path = content_dir / "b.md"
    _write_markdown(article_path, "Article B", "# Intro\nline one")

    indexer = KBIndexer(db=db, content_dir=str(content_dir), chunk_size_chars=80)
    indexer.index_all()
    docs = db.get_recent_kb_documents(limit=5)
    doc = next((item for item in docs if str(item.get("markdown_path", "")).endswith("b.md")), None)
    assert doc is not None

    with sqlite3.connect(db.db_path) as conn:
        first_chunks = conn.execute(
            "SELECT COUNT(*) FROM kb_chunks WHERE document_id = ?",
            (doc["id"],),
        ).fetchone()[0]

    _write_markdown(article_path, "Article B", "# Intro\nline one\nline two\nline three")
    result = indexer.index_paths([article_path])

    with sqlite3.connect(db.db_path) as conn:
        second_chunks = conn.execute(
            "SELECT COUNT(*) FROM kb_chunks WHERE document_id = ?",
            (doc["id"],),
        ).fetchone()[0]

    assert result.indexed_files == 1
    assert second_chunks >= first_chunks


def test_indexer_logs_partial_failures_and_continues(tmp_path) -> None:
    """One unreadable markdown file does not stop full indexing pass."""
    db = Database(str(tmp_path / "test.db"))
    content_dir = tmp_path / "vault" / "raw" / "url-saves"
    content_dir.mkdir(parents=True)

    valid_path = content_dir / "valid.md"
    _write_markdown(valid_path, "Good", "# Good\nhello")

    broken_path = content_dir / "broken.md"
    broken_path.write_bytes(b"\x80\x81\x82")

    indexer = KBIndexer(db=db, content_dir=str(content_dir), chunk_size_chars=200)
    result = indexer.index_all()

    assert result.scanned_files == 2
    assert result.indexed_files == 1
    assert result.failed_files == 1

    with sqlite3.connect(db.db_path) as conn:
        failures = conn.execute("SELECT COUNT(*) FROM kb_ingest_log").fetchone()[0]
    assert failures == 1
