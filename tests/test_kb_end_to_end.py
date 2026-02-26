"""End-to-end fixture for save -> index -> answer preparation flow."""

from __future__ import annotations

from jarvis.database import Database
from jarvis.kb_indexer import KBIndexer
from jarvis.kb_prompting import build_grounded_prompt
from jarvis.kb_retrieval import retrieve_chunks


def test_save_index_answer_flow_fixture(tmp_path) -> None:
    """A saved markdown file can be indexed and retrieved for grounded prompting."""
    db = Database(str(tmp_path / "test.db"))
    content_dir = tmp_path / ".jarvis" / "url-saves"
    content_dir.mkdir(parents=True)

    article = content_dir / "saved.md"
    article.write_text(
        "---\n"
        "url: https://example.com/sqlite-kb\n"
        "title: SQLite KB\n"
        "captured_at: 2026-01-01T00:00:00Z\n"
        "---\n\n"
        "# Intro\n"
        "SQLite FTS5 enables lexical retrieval for knowledge bases.\n",
        encoding="utf-8",
    )

    indexer = KBIndexer(db=db, content_dir=str(content_dir), chunk_size_chars=200)
    result = indexer.index_all()
    assert result.indexed_files == 1

    chunks = retrieve_chunks(db, "How does lexical retrieval work?", limit=3)
    assert chunks

    prompt = build_grounded_prompt("How does lexical retrieval work?", chunks)
    assert "[doc:" in prompt
    assert "SQLite FTS5" in prompt
