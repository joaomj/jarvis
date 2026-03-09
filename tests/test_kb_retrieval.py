"""Tests for KB lexical retrieval and diversity behavior."""

from __future__ import annotations

from jarvis.database import Database
from jarvis.kb_retrieval import build_fts_query, retrieve_chunks


def _seed_document(db: Database, path: str, title: str, content_hash: str, texts: list[str]) -> int:
    doc_id = db.upsert_document(
        markdown_path=path,
        url_original=f"https://example.com/{title}",
        url_canonical=f"https://example.com/{title}",
        title=title,
        domain="example.com",
        captured_at="2026-01-01T00:00:00Z",
        content_hash=content_hash,
    )
    db.replace_document_chunks(
        doc_id,
        [
            {
                "chunk_index": index,
                "heading": "Section",
                "line_start": 1,
                "line_end": 2,
                "chunk_text": text,
            }
            for index, text in enumerate(texts)
        ],
    )
    db.upsert_fts_for_document(doc_id)
    return doc_id


def test_build_fts_query_sanitizes_terms() -> None:
    query = build_fts_query("Considering my knowledge base, what about SQLite + Python?")

    assert "sqlite" in query
    assert "python" in query
    assert "considering" in query


def test_retrieve_chunks_applies_diversity_cap(tmp_path) -> None:
    db = Database(str(tmp_path / "test.db"))
    doc1 = _seed_document(
        db,
        ".jarvis/url-saves/doc1.md",
        "Doc1",
        "hash-1",
        ["python sqlite indexing", "python sqlite testing", "python sqlite tuning"],
    )
    doc2 = _seed_document(
        db,
        ".jarvis/url-saves/doc2.md",
        "Doc2",
        "hash-2",
        ["python retrieval architecture", "sqlite query patterns"],
    )

    chunks = retrieve_chunks(db, "python sqlite", limit=4, per_document_cap=1)
    doc_counts: dict[int, int] = {}
    for chunk in chunks:
        doc_counts[chunk.document_id] = doc_counts.get(chunk.document_id, 0) + 1

    assert doc1 in doc_counts
    assert doc2 in doc_counts
    assert all(count <= 1 for count in doc_counts.values())


def test_retrieve_chunks_returns_empty_for_unmatched_query(tmp_path) -> None:
    db = Database(str(tmp_path / "test.db"))
    _seed_document(
        db,
        ".jarvis/url-saves/doc3.md",
        "Doc3",
        "hash-3",
        ["observability metrics and alerts"],
    )

    chunks = retrieve_chunks(db, "quantum tunneling", limit=3)
    assert chunks == []
