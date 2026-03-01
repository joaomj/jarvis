"""Tests for attachment ingestion and retrieval priority."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.bot import JarvisBot
from jarvis.config import Settings
from jarvis.kb_retrieval import retrieve_chunks


@pytest.fixture
def settings(tmp_path):
    """Create test settings for attachment ingestion."""
    db_path = tmp_path / "test.db"
    return Settings(
        telegram_bot_id="test_token",
        telegram_user_id=123456789,
        telegram_polling_interval=1.0,
        telegram_polling_timeout=30,
        opencode_url="http://localhost:4096",
        opencode_server_password="test_password",
        database_path=str(db_path),
        enable_message_audit=True,
        vault_root=str(tmp_path / "vault"),
        kb_content_dir=str(tmp_path / "vault" / "sources"),
    )


@pytest.mark.asyncio
async def test_text_attachment_is_saved_and_indexed(settings) -> None:
    """Text attachments are persisted under vault and indexed for retrieval."""
    bot = JarvisBot(settings)

    fake_file = MagicMock()
    fake_file.download_as_bytearray = AsyncMock(
        return_value=bytearray(b"Federalist papers discuss factions")
    )

    bot.app = SimpleNamespace(bot=MagicMock())
    bot.app.bot.get_file = AsyncMock(return_value=fake_file)

    update = MagicMock()
    message = MagicMock()
    message.chat_id = 100
    message.message_id = 200
    message.document = SimpleNamespace(
        file_id="file-123",
        file_unique_id="unique-123",
        file_name="notes.txt",
        mime_type="text/plain",
    )
    update.effective_message = message

    result = await bot._ingest_attachment_if_present(update)

    assert result is not None
    assert "attachments" in result.markdown_path
    chunks = retrieve_chunks(bot.db, "factions", limit=3)
    assert chunks


def test_retrieve_chunks_prefers_attachment_paths() -> None:
    """Attachment chunks are prioritized over non-attachment chunks."""

    class FakeDB:
        def search_chunks_fts(self, query: str, limit: int) -> list[dict[str, object]]:
            return [
                {
                    "document_id": 1,
                    "chunk_index": 0,
                    "heading": "Web",
                    "line_start": 1,
                    "line_end": 2,
                    "chunk_text": "general source",
                    "title": "General",
                    "url_original": "https://example.com",
                    "markdown_path": "vault/sources/web/general.md",
                    "score": -10.0,
                },
                {
                    "document_id": 2,
                    "chunk_index": 0,
                    "heading": "Attachment",
                    "line_start": 1,
                    "line_end": 2,
                    "chunk_text": "attached source",
                    "title": "Attachment",
                    "url_original": None,
                    "markdown_path": "vault/sources/attachments/note.md",
                    "score": -1.0,
                },
            ]

    chunks = retrieve_chunks(FakeDB(), "source", limit=1)
    assert chunks
    assert "attachments" in chunks[0].markdown_path
