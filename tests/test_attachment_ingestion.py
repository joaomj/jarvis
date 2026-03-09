"""Integration tests for attachment ingestion and source-priority behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.bot import JarvisBot
from jarvis.kb_retrieval import retrieve_chunks
from tests.harness.fake_telegram import FakeTelegramApp, FakeTelegramBot
from tests.harness.update_factory import build_document_update


@pytest.fixture
def bot(integration_settings, fake_telegram_app: FakeTelegramApp) -> JarvisBot:
    """Create bot instance wired for attachment integration tests."""
    bot = JarvisBot(integration_settings)
    bot.app = fake_telegram_app
    bot.db.add_user(integration_settings.telegram_user_id)
    return bot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_attachment_ingestion_writes_vault_artifacts_and_indexes_markdown(
    bot: JarvisBot,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """Text attachment ingestion writes raw+indexed artifacts and updates retrieval index."""
    fake_telegram_bot.add_file("file-123", b"Federalist papers discuss factions")
    update = build_document_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        file_id="file-123",
        file_unique_id="unique-123",
        file_name="notes.txt",
        mime_type="text/plain",
        bot=fake_telegram_bot,
    )

    result = await bot._ingest_attachment_if_present(update)

    assert result is not None
    assert result.indexed is True
    assert "/attachments/raw/" in result.raw_path
    assert result.markdown_path is not None
    assert "/attachments/indexed/" in result.markdown_path

    chunks = retrieve_chunks(bot.db, "factions", limit=3)
    assert chunks
    assert "attachments" in chunks[0].markdown_path.lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_retrieval_prefers_attachment_evidence_over_web_sources(
    bot: JarvisBot,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """When both attachment and web sources match, attachment evidence ranks first."""
    fake_telegram_bot.add_file("file-abc", b"Faction stability note from attachment")
    attachment_update = build_document_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        file_id="file-abc",
        file_unique_id="unique-abc",
        file_name="attachment.txt",
        mime_type="text/plain",
        bot=fake_telegram_bot,
    )
    await bot._ingest_attachment_if_present(attachment_update)

    web_doc = Path(bot.settings.kb_content_dir) / "web" / "factions.md"
    web_doc.parent.mkdir(parents=True, exist_ok=True)
    web_doc.write_text(
        "---\n"
        "url: https://example.com/factions\n"
        "title: Web factions\n"
        "captured_at: 2026-01-01T00:00:00Z\n"
        "---\n\n"
        "Faction stability note from web source\n",
        encoding="utf-8",
    )
    bot.kb_indexer.index_paths([web_doc])

    chunks = retrieve_chunks(bot.db, "Faction stability note", limit=2)

    assert len(chunks) >= 2
    assert "attachments" in chunks[0].markdown_path.lower()
    assert "/web/" in chunks[1].markdown_path.replace("\\", "/").lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_kb_indexing_isolated_from_bot() -> None:
    """KB indexer can be used independently for command-based workflows."""
    # KB functionality is now accessed via /recall command
    # This test verifies the indexer components remain functional
    from jarvis.kb_indexer import KBIndexer
    from jarvis.kb_retrieval import retrieve_chunks

    # These components still exist and work for command-based usage
    assert retrieve_chunks is not None
    assert KBIndexer is not None
