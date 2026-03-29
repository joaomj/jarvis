"""Tests for KB database schema and storage operations."""

from __future__ import annotations

import sqlite3

from jarvis.database import Database


def test_kb_tables_created_on_fresh_db(tmp_path) -> None:
    """Fresh DB initialization creates KB tables and FTS index."""
    db_path = tmp_path / "fresh.db"
    db = Database(str(db_path))

    with sqlite3.connect(db.db_path) as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }

    assert "kb_documents" in names
    assert "kb_chunks" in names
    assert "kb_chunks_fts" in names
    assert "kb_ingest_log" in names

    document_id = db.upsert_document(
        markdown_path="vault/raw/url-saves/example.md",
        url_original="https://example.com/post",
        url_canonical="https://example.com/post",
        title="Example",
        domain="example.com",
        captured_at="2026-01-01T00:00:00Z",
        content_hash="hash-1",
    )
    db.replace_document_chunks(
        document_id,
        [
            {
                "chunk_index": 0,
                "heading": "Intro",
                "line_start": 1,
                "line_end": 3,
                "chunk_text": "python sqlite retrieval",
            }
        ],
    )
    db.upsert_fts_for_document(document_id)

    rows = db.search_chunks_fts("python", limit=5)
    assert rows
    assert rows[0]["document_id"] == document_id


def test_kb_migration_is_non_destructive_for_existing_db(tmp_path) -> None:
    """Existing DB migrates in-place without dropping prior data."""
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE users (telegram_id INTEGER PRIMARY KEY, allowed BOOLEAN)")
        conn.execute("INSERT INTO users (telegram_id, allowed) VALUES (123, 1)")

    db = Database(str(db_path))

    assert db.is_user_allowed(123)
    document_id = db.upsert_document(
        markdown_path="vault/raw/url-saves/legacy.md",
        url_original="https://legacy.example.com",
        url_canonical="https://legacy.example.com",
        title="Legacy",
        domain="legacy.example.com",
        captured_at="2026-01-01T00:00:00Z",
        content_hash="hash-legacy",
    )
    assert document_id > 0
