"""Tests for KB/save intent routing behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.bot import JarvisBot
from jarvis.config import Settings
from jarvis.kb_retrieval import RetrievedChunk


@pytest.fixture
def settings(tmp_path):
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
    )


def test_save_intent_detects_url_only_message(settings) -> None:
    bot = JarvisBot(settings)

    assert bot._is_save_intent("https://example.com/article") is True
    assert bot._is_save_intent("save this https://example.com/article for read later") is True
    assert bot._is_save_intent("save this for later") is False


def test_bookmark_query_matching_still_works(settings) -> None:
    bot = JarvisBot(settings)

    assert bot._is_bookmark_query("What did I save last week?") is True
    assert bot._is_bookmark_query("save https://example.com/article") is False


@pytest.mark.asyncio
async def test_process_input_prefers_save_handler_for_save_intent(settings) -> None:
    bot = JarvisBot(settings)
    bot.model_selector = None
    bot.events.handle_interaction_input = AsyncMock(return_value=False)
    bot._is_save_intent = MagicMock(return_value=True)
    bot._handle_save_intent = AsyncMock(return_value=True)
    bot._is_bookmark_query = MagicMock(return_value=False)

    update = MagicMock()
    update.effective_message.chat_id = 100
    update.effective_message.message_id = 200
    bot.opencode = MagicMock()

    result = await bot._process_input(
        update, user_id=123, session_id="sess-1", text="https://x.com"
    )

    assert result is None
    bot._handle_save_intent.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_input_routes_kb_questions_before_bookmarks(settings) -> None:
    bot = JarvisBot(settings)
    bot.model_selector = None
    bot.events.handle_interaction_input = AsyncMock(return_value=False)
    bot._is_save_intent = MagicMock(return_value=False)
    bot._is_kb_answer_intent = MagicMock(return_value=True)
    bot._handle_kb_answer_intent = AsyncMock(return_value=([{"type": "text", "text": "ok"}], {}))
    bot._is_bookmark_query = MagicMock(return_value=True)

    update = MagicMock()
    update.effective_message.chat_id = 100
    update.effective_message.message_id = 200

    result = await bot._process_input(
        update,
        user_id=123,
        session_id="sess-2",
        text="considering my knowledge base, what is this?",
    )

    assert result == ([{"type": "text", "text": "ok"}], {})
    bot._handle_kb_answer_intent.assert_awaited_once()


@pytest.mark.asyncio
async def test_kb_answer_without_citations_returns_insufficient_evidence(
    settings, monkeypatch
) -> None:
    bot = JarvisBot(settings)
    bot.model_selector = None
    bot.opencode = MagicMock()
    bot.opencode.send_message = AsyncMock(
        return_value=([{"type": "text", "text": "Here is an answer with no citations."}], {})
    )

    monkeypatch.setattr(
        "jarvis.bot_kb.retrieve_chunks",
        lambda *_args, **_kwargs: [
            RetrievedChunk(
                document_id=1,
                chunk_index=0,
                heading="Intro",
                line_start=1,
                line_end=2,
                chunk_text="SQLite keeps lexical chunks.",
                title="Doc",
                url_original="https://example.com",
                markdown_path=".jarvis/url-saves/doc.md",
                score=-1.0,
            )
        ],
    )

    parts, _info = await bot._handle_kb_answer_intent(
        user_id=123,
        session_id="sess-3",
        text="from what I saved, explain indexing",
    )

    text = parts[0]["text"].lower()
    assert "do not have enough evidence" in text


@pytest.mark.asyncio
async def test_kb_answer_falls_back_to_web_when_local_missing(settings, monkeypatch) -> None:
    """When local retrieval is empty, bot can return sourced web fallback answer."""
    bot = JarvisBot(settings)
    bot.model_selector = None
    bot.opencode = MagicMock()
    bot.opencode.send_message = AsyncMock(
        side_effect=[
            (
                [
                    {
                        "type": "text",
                        "text": '{"sources":[{"title":"Federalist Papers","url":"https://example.com/fed","why_relevant":"primary source"}]}',
                    }
                ],
                {},
            ),
            (
                [{"type": "text", "text": "Factions are discussed as a core risk [web:1]."}],
                {},
            ),
        ]
    )

    monkeypatch.setattr("jarvis.bot_kb.retrieve_chunks", lambda *_args, **_kwargs: [])

    parts, _info = await bot._handle_kb_answer_intent(
        user_id=123,
        session_id="sess-web-fallback",
        text="what does federalist papers say about factions?",
    )

    text = parts[0]["text"]
    assert "[web:1]" in text
    assert "Sources:" in text
