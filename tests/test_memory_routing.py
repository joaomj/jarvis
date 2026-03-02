"""Integration tests for memory behavior contracts."""

from __future__ import annotations

import json

import pytest

from jarvis.bot import JarvisBot
from tests.harness.fake_opencode_server import FakeOpenCodeServer
from tests.harness.fake_telegram import FakeTelegramApp, FakeTelegramBot
from tests.harness.update_factory import build_message_update


def _memory_decision_response(
    *,
    action: str,
    payload: str,
    needs_confirmation: bool = False,
    confirmation_question: str = "",
) -> dict[str, object]:
    return {
        "parts": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "action": action,
                        "payload": payload,
                        "needs_confirmation": needs_confirmation,
                        "confirmation_question": confirmation_question,
                    }
                ),
            }
        ],
        "info": {"modelID": "gpt-4o", "providerID": "openai", "agent": "dr-gate"},
    }


@pytest.fixture
def bot(integration_settings, fake_telegram_app: FakeTelegramApp) -> JarvisBot:
    """Create bot instance wired for memory integration tests."""
    bot = JarvisBot(integration_settings)
    bot.app = fake_telegram_app
    bot.db.add_user(integration_settings.telegram_user_id)
    bot.model_selector = None
    return bot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_remember_writes_vault_file_and_db_index(
    bot: JarvisBot,
    fake_opencode_client,
    fake_opencode_server: FakeOpenCodeServer,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """Remember flow stores a vault artifact and active DB row."""
    bot.opencode = fake_opencode_client
    fake_opencode_server.message_response = _memory_decision_response(
        action="remember",
        payload="Tocqueville warns about soft despotism",
    )
    update = build_message_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        text="remember Tocqueville warns about soft despotism",
        message_id=10,
        bot=fake_telegram_bot,
    )

    handled = await bot._handle_memory_intent(
        update,
        user_id=bot.settings.telegram_user_id,
        session_id="sess-memory",
        text=update.effective_message.text or "",
    )

    assert handled is True
    records = bot.memory_store.search("soft despotism", limit=5)
    assert len(records) == 1
    assert records[0].markdown_path.endswith(".md")
    assert fake_telegram_bot.sent_messages[-1].text.startswith("Saved to memory")

    row = bot.db.get_memory_by_key(records[0].memory_key)
    assert row is not None
    assert int(row["active"]) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_forget_marks_inactive_and_excludes_recall(
    bot: JarvisBot,
    fake_opencode_client,
    fake_opencode_server: FakeOpenCodeServer,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """Forget flow deactivates memory and removes it from recall results."""
    bot.opencode = fake_opencode_client
    remember_update = build_message_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        text="remember faction risk",
        message_id=11,
        bot=fake_telegram_bot,
    )
    fake_opencode_server.message_response = _memory_decision_response(
        action="remember",
        payload="Faction risk in republics",
    )
    await bot._handle_memory_intent(
        remember_update,
        user_id=bot.settings.telegram_user_id,
        session_id="sess-memory",
        text=remember_update.effective_message.text or "",
    )
    memory_key = bot.memory_store.search("Faction risk", limit=1)[0].memory_key

    forget_update = build_message_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        text="forget faction risk",
        message_id=12,
        bot=fake_telegram_bot,
    )
    fake_opencode_server.message_response = _memory_decision_response(
        action="forget",
        payload="Faction risk",
    )
    handled = await bot._handle_memory_intent(
        forget_update,
        user_id=bot.settings.telegram_user_id,
        session_id="sess-memory",
        text=forget_update.effective_message.text or "",
    )

    assert handled is True
    assert bot.memory_store.search("Faction risk", limit=5) == []
    row = bot.db.get_memory_by_key(memory_key)
    assert row is not None
    assert int(row["active"]) == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_recall_returns_deterministic_top_k_format(
    bot: JarvisBot,
    fake_opencode_client,
    fake_opencode_server: FakeOpenCodeServer,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """Recall responses return ordered top-k list with numbered snippets."""
    bot.opencode = fake_opencode_client
    for idx in range(3):
        fake_opencode_server.message_response = _memory_decision_response(
            action="remember",
            payload=f"Faction source {idx}",
        )
        remember_update = build_message_update(
            user_id=bot.settings.telegram_user_id,
            chat_id=100,
            text=f"remember faction source {idx}",
            message_id=20 + idx,
            bot=fake_telegram_bot,
        )
        await bot._handle_memory_intent(
            remember_update,
            user_id=bot.settings.telegram_user_id,
            session_id="sess-memory",
            text=remember_update.effective_message.text or "",
        )

    fake_opencode_server.message_response = _memory_decision_response(
        action="recall",
        payload="Faction",
    )
    recall_update = build_message_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        text="what do you recall about faction",
        message_id=40,
        bot=fake_telegram_bot,
    )
    handled = await bot._handle_memory_intent(
        recall_update,
        user_id=bot.settings.telegram_user_id,
        session_id="sess-memory",
        text=recall_update.effective_message.text or "",
    )

    assert handled is True
    response = fake_telegram_bot.sent_messages[-1].text
    assert response.startswith("Here is what I remember:")
    assert "1. [" in response
    assert "2. [" in response
    assert "3. [" in response


@pytest.mark.integration
@pytest.mark.asyncio
async def test_uncertain_intent_triggers_confirmation_prompt(
    bot: JarvisBot,
    fake_opencode_client,
    fake_opencode_server: FakeOpenCodeServer,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """Ambiguous intent prompts user confirmation instead of writing memory."""
    bot.opencode = fake_opencode_client
    fake_opencode_server.message_response = _memory_decision_response(
        action="remember",
        payload="Maybe store this",
        needs_confirmation=True,
        confirmation_question="Do you want me to remember this note?",
    )
    update = build_message_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        text="this might be important",
        message_id=50,
        bot=fake_telegram_bot,
    )

    handled = await bot._handle_memory_intent(
        update,
        user_id=bot.settings.telegram_user_id,
        session_id="sess-memory",
        text=update.effective_message.text or "",
    )

    assert handled is True
    assert fake_telegram_bot.sent_messages[-1].text == "Do you want me to remember this note?"
    assert bot.memory_store.search("Maybe store this", limit=5) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_private_memory_turn_skips_incoming_audit_log(
    bot: JarvisBot,
    fake_opencode_client,
    fake_opencode_server: FakeOpenCodeServer,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """Private memory turns can store memory without persisting incoming audit message."""
    bot.opencode = fake_opencode_client
    before_count = bot.db.get_user_message_count(bot.settings.telegram_user_id)

    bot._log_incoming_message(
        bot.settings.telegram_user_id,
        "private: remember this only for me",
        persist=False,
    )

    fake_opencode_server.message_response = _memory_decision_response(
        action="remember",
        payload="only for me",
    )
    update = build_message_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        text="remember this only for me",
        message_id=60,
        bot=fake_telegram_bot,
    )
    await bot._handle_memory_intent(
        update,
        user_id=bot.settings.telegram_user_id,
        session_id="sess-memory",
        text=update.effective_message.text or "",
    )

    after_count = bot.db.get_user_message_count(bot.settings.telegram_user_id)
    assert before_count == after_count
    assert bot.memory_store.search("only for me", limit=5)
