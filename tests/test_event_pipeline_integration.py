"""Integration tests for event processor and interaction pipeline."""

from __future__ import annotations

import pytest

from jarvis.bot import JarvisBot
from tests.harness.fake_opencode_server import FakeOpenCodeServer
from tests.harness.fake_telegram import FakeTelegramApp, FakeTelegramBot
from tests.harness.update_factory import build_callback_update, build_message_update


@pytest.fixture
def bot(integration_settings, fake_telegram_app: FakeTelegramApp) -> JarvisBot:
    """Create bot instance wired with fake Telegram app."""
    bot = JarvisBot(integration_settings)
    bot.app = fake_telegram_app
    bot.db.add_user(integration_settings.telegram_user_id)
    return bot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_event_pipeline_completion_delivers_response_and_persists_turn(
    bot: JarvisBot,
    fake_opencode_client,
    fake_opencode_server: FakeOpenCodeServer,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """Pending prompts complete via message.updated and create persisted turns."""
    bot.opencode = fake_opencode_client
    fake_opencode_server.message_history["sess-1"] = [
        {
            "info": {
                "role": "assistant",
                "modelID": "gpt-4o",
                "providerID": "openai",
                "agent": "build",
            },
            "parts": [{"type": "text", "text": "Final answer from OpenCode."}],
        }
    ]

    bot.events.register_pending_prompt(
        session_id="sess-1",
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        in_message_id=200,
        prompt_text="summarize",
        session_title="jarvis-session",
    )

    await bot.events._handle_event(
        {
            "type": "message.updated",
            "properties": {
                "info": {
                    "sessionID": "sess-1",
                    "role": "assistant",
                    "time": {"completed": True},
                    "modelID": "gpt-4o",
                    "providerID": "openai",
                    "agent": "build",
                }
            },
        }
    )

    assert bot.events.has_pending_prompt("sess-1") is False
    turn = bot.db.get_turn(1)
    assert turn is not None
    assert turn["response_text"] == "Final answer from OpenCode."
    assert fake_telegram_bot.sent_messages[-1].text == r"Final answer from OpenCode\."


@pytest.mark.integration
@pytest.mark.asyncio
async def test_private_completion_replies_without_turn_persistence(
    bot: JarvisBot,
    fake_opencode_client,
    fake_opencode_server: FakeOpenCodeServer,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """Private pending prompts skip turn persistence while still replying."""
    bot.opencode = fake_opencode_client
    fake_opencode_server.message_history["sess-private"] = [
        {
            "info": {
                "role": "assistant",
                "modelID": "gpt-4o-mini",
                "providerID": "openai",
                "agent": "build",
            },
            "parts": [{"type": "text", "text": "Private answer."}],
        }
    ]

    bot.events.register_pending_prompt(
        session_id="sess-private",
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        in_message_id=201,
        prompt_text="private prompt",
        session_title="jarvis-session",
        is_private=True,
    )

    await bot.events._handle_event(
        {
            "type": "message.updated",
            "properties": {
                "info": {
                    "sessionID": "sess-private",
                    "role": "assistant",
                    "time": {"completed": True},
                    "modelID": "gpt-4o-mini",
                    "providerID": "openai",
                    "agent": "build",
                }
            },
        }
    )

    assert bot.db.get_turn(1) is None
    assert fake_telegram_bot.sent_messages[-1].text == r"Private answer\."


@pytest.mark.integration
@pytest.mark.asyncio
async def test_question_and_permission_interactions_roundtrip_via_callbacks(
    bot: JarvisBot,
    fake_opencode_client,
    fake_opencode_server: FakeOpenCodeServer,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """question.asked and permission.asked interactions complete through callbacks."""
    bot.opencode = fake_opencode_client
    bot.events.remember_chat(100)

    await bot.events._handle_event(
        {
            "type": "question.asked",
            "properties": {
                "id": "req-1",
                "sessionID": "sess-1",
                "questions": [{"question": "Choose", "options": [{"label": "A"}]}],
            },
        }
    )
    answer_update = build_message_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        text="/answer A",
        message_id=300,
        bot=fake_telegram_bot,
    )
    consumed = await bot.events.handle_interaction_input(
        answer_update,
        bot.settings.telegram_user_id,
        "/answer A",
    )

    await bot.events._handle_event(
        {
            "type": "permission.asked",
            "properties": {
                "id": "perm-1",
                "sessionID": "sess-1",
                "permission": "bash",
                "patterns": ["rm -rf"],
            },
        }
    )
    callback_update = build_callback_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        data="perm:perm-1:once",
        message_id=301,
        bot=fake_telegram_bot,
    )
    callback_handled = await bot.events.handle_callback(callback_update)

    assert consumed is True
    assert callback_handled is True
    assert fake_opencode_server.question_replies["req-1"][0]["answers"] == [["A"]]
    assert fake_opencode_server.permission_replies["perm-1"][0]["reply"] == "once"
    assert fake_telegram_bot.edited_reply_markups[-1].message_id == 301


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pinned_status_updates_on_session_diff_and_message_metadata(
    bot: JarvisBot,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """Pinned status reflects diff and token/model updates from event lifecycle."""
    bot.events.register_pending_prompt(
        session_id="sess-pinned",
        user_id=bot.settings.telegram_user_id,
        chat_id=111,
        in_message_id=9,
        prompt_text="status",
        session_title="jarvis-pinned",
    )

    bot.events._pinned._last_publish_ts = 0.0
    await bot.events._handle_event(
        {
            "type": "session.diff",
            "properties": {"diff": [{"file": "src/jarvis/bot.py", "additions": 3, "deletions": 1}]},
        }
    )

    bot.events._pinned._last_publish_ts = 0.0
    await bot.events._handle_event(
        {
            "type": "message.updated",
            "properties": {
                "info": {
                    "sessionID": "sess-pinned",
                    "role": "assistant",
                    "time": {"completed": False},
                    "modelID": "gpt-4o",
                    "providerID": "openai",
                    "agent": "build",
                    "tokens": {"input": 8, "cache": {"read": 2}},
                }
            },
        }
    )

    assert fake_telegram_bot.pinned_messages
    assert "Changed files: 1" in fake_telegram_bot.sent_messages[0].text
    assert fake_telegram_bot.edited_texts
    assert "Context: ~10 tokens" in fake_telegram_bot.edited_texts[-1].text
