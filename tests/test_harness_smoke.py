"""Smoke tests for shared test harness components."""

from __future__ import annotations

import pytest

from tests.harness.fake_opencode_server import build_opencode_client
from tests.harness.fake_telegram import FakeTelegramBot
from tests.harness.update_factory import (
    build_callback_update,
    build_document_update,
    build_message_update,
)


@pytest.mark.fast
@pytest.mark.asyncio
async def test_fake_telegram_bot_send_edit_and_file_roundtrip() -> None:
    """Fake Telegram bot captures send/edit calls deterministically."""
    bot = FakeTelegramBot()
    bot.add_file("file-1", b"hello")

    sent = await bot.send_message(chat_id=100, text="hello", reply_to_message_id=9)
    await bot.edit_message_reply_markup(chat_id=100, message_id=sent.message_id, reply_markup=None)
    file_obj = await bot.get_file("file-1")

    assert sent.message_id == 100
    assert bot.sent_messages[0].text == "hello"
    assert bot.edited_reply_markups[0].message_id == 100
    assert await file_obj.download_as_bytearray() == bytearray(b"hello")


@pytest.mark.fast
def test_update_factory_builds_message_callback_and_document_shapes() -> None:
    """Update factory creates typed update payloads for key Telegram flows."""
    message_update = build_message_update(user_id=1, chat_id=2, text="ping")
    callback_update = build_callback_update(user_id=1, chat_id=2, data="perm:req:once")
    document_update = build_document_update(
        user_id=1,
        chat_id=2,
        file_id="f1",
        file_unique_id="u1",
        file_name="doc.txt",
        mime_type="text/plain",
    )

    assert message_update.effective_message is not None
    assert message_update.effective_message.text == "ping"
    assert callback_update.callback_query is not None
    assert callback_update.callback_query.data == "perm:req:once"
    assert document_update.effective_message is not None
    assert document_update.effective_message.document.file_name == "doc.txt"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fake_opencode_server_supports_json_and_sse(fake_opencode_server) -> None:
    """Fake OpenCode server serves JSON endpoints and SSE stream."""
    fake_opencode_server.queue_sse_events(
        [
            'event: message.updated\ndata: {"type":"message.updated","properties":{"id":"m1"}}',
            'event: session.diff\ndata: {"type":"session.diff","properties":{"diff":[]}}',
        ]
    )
    client = await build_opencode_client(fake_opencode_server)
    try:
        session_id = await client.create_session("smoke")
        await client.prompt_async(session_id, "hello", agent="dr-gate")
        events = [event async for event in client.stream_events()]
    finally:
        await client.close()

    assert session_id == "sess-1"
    assert fake_opencode_server.prompt_payloads[session_id][0]["agent"] == "dr-gate"
    assert [event["type"] for event in events] == ["message.updated", "session.diff"]
