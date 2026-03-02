"""Integration tests for deep research workflow and callbacks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jarvis.bot import JarvisBot
from tests.harness.fake_opencode_server import FakeOpenCodeServer
from tests.harness.fake_telegram import FakeTelegramApp, FakeTelegramBot
from tests.harness.update_factory import build_callback_update, build_message_update


def _json_response(payload: dict[str, object], agent: str) -> dict[str, object]:
    return {
        "parts": [{"type": "text", "text": json.dumps(payload)}],
        "info": {"modelID": "gpt-4o", "providerID": "openai", "agent": agent},
    }


def _text_response(text: str, agent: str) -> dict[str, object]:
    return {
        "parts": [{"type": "text", "text": text}],
        "info": {"modelID": "gpt-4o", "providerID": "openai", "agent": agent},
    }


def _configure_research_stage_responses(server: FakeOpenCodeServer) -> None:
    server.set_agent_message_response(
        "dr-planner",
        _json_response({"sections": [{"id": "s1", "heading": "Intro"}]}, "dr-planner"),
    )
    server.set_agent_message_response(
        "dr-query-builder",
        _json_response({"queries": ["history of factions"]}, "dr-query-builder"),
    )
    server.set_agent_message_response(
        "dr-websearch-highrep",
        _json_response(
            {"sources": [{"title": "Source", "url": "https://example.com"}]},
            "dr-websearch-highrep",
        ),
    )
    server.set_agent_message_response(
        "dr-source-triage",
        _json_response({"selected": [{"url_or_path": "https://example.com"}]}, "dr-source-triage"),
    )
    server.set_agent_message_response(
        "dr-evidence-extractor",
        _json_response(
            {"evidence_units": [{"evidence_id": "E1", "text": "quote"}]},
            "dr-evidence-extractor",
        ),
    )
    server.set_agent_message_response(
        "dr-section-writer",
        _text_response("## Intro\nText [E1].", "dr-section-writer"),
    )
    server.set_agent_message_response(
        "dr-editor-integrator",
        _text_response("# Report\nClaim [E1].\n\n## References\n- Source", "dr-editor-integrator"),
    )
    server.set_agent_message_response(
        "dr-citation-auditor",
        _json_response(
            {"issues": [], "stats": {"uncited_claim_count": 0}},
            "dr-citation-auditor",
        ),
    )


@pytest.fixture
def bot(integration_settings, fake_telegram_app: FakeTelegramApp) -> JarvisBot:
    """Create bot instance wired for deep-research integration tests."""
    bot = JarvisBot(integration_settings)
    bot.app = fake_telegram_app
    bot.db.add_user(integration_settings.telegram_user_id)
    bot.model_selector = None
    return bot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deep_research_run_job_preserves_stage_order_and_writes_artifacts(
    bot: JarvisBot,
    fake_opencode_client,
    fake_opencode_server: FakeOpenCodeServer,
) -> None:
    """run_job executes deterministic stage order and writes expected workspace artifacts."""
    bot.opencode = fake_opencode_client
    _configure_research_stage_responses(fake_opencode_server)

    result = await bot.deep_research.run_job(
        opencode=bot.opencode,
        session_id="sess-stage-order",
        user_id=bot.settings.telegram_user_id,
        question="What are the strongest arguments about factions?",
    )

    payloads = fake_opencode_server.message_payloads["sess-stage-order"]
    stage_order = [str(payload.get("agent", "")) for payload in payloads]
    assert stage_order == [
        "dr-planner",
        "dr-query-builder",
        "dr-websearch-highrep",
        "dr-source-triage",
        "dr-evidence-extractor",
        "dr-section-writer",
        "dr-editor-integrator",
        "dr-citation-auditor",
    ]

    workspace = Path(result.workspace_path)
    assert (workspace / "question.md").exists()
    assert (workspace / "plan.json").exists()
    assert (workspace / "queries.json").exists()
    assert (workspace / "sources.json").exists()
    assert (workspace / "triage.json").exists()
    assert (workspace / "evidence.json").exists()
    assert (workspace / "section.md").exists()
    assert (workspace / "report.md").exists()
    assert (workspace / "audit.json").exists()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deep_research_confirm_callback_starts_job_and_emits_completion(
    bot: JarvisBot,
    fake_opencode_client,
    fake_opencode_server: FakeOpenCodeServer,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """Confirm callback starts deep research job and writes workspace artifacts."""
    bot.opencode = fake_opencode_client
    _configure_research_stage_responses(fake_opencode_server)
    fake_opencode_server.set_agent_message_response(
        "dr-gate",
        _json_response(
            {
                "effort": "deep",
                "needs_deep_confirmation": True,
                "suggested_user_confirmation": "Run deep research now?",
                "why": "broad report request",
            },
            "dr-gate",
        ),
    )

    update = build_message_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        text="Please run deep research and write a 10-page report",
        message_id=10,
        bot=fake_telegram_bot,
    )
    handled = await bot._maybe_handle_deep_research(
        update=update,
        user_id=bot.settings.telegram_user_id,
        session_id="sess-confirm",
        text=update.effective_message.text or "",
    )

    token = next(iter(bot._research_pending.keys()))
    callback_update = build_callback_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        data=f"dr:confirm:{token}",
        message_id=11,
        bot=fake_telegram_bot,
    )
    callback_handled = await bot._handle_research_callback(callback_update)

    assert handled is True
    assert callback_handled is True
    assert bot._research_pending == {}
    assert any(
        msg.text.startswith("Deep research started") for msg in fake_telegram_bot.sent_messages
    )
    assert any(
        msg.text.startswith("Deep research completed") for msg in fake_telegram_bot.sent_messages
    )
    assert "sess-confirm" in fake_opencode_server.message_payloads
    assert len(fake_opencode_server.message_payloads["sess-confirm"]) == 9


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deep_research_cancel_callback_does_not_execute_job(
    bot: JarvisBot,
    fake_opencode_client,
    fake_opencode_server: FakeOpenCodeServer,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """Cancel callback clears pending request and prevents stage execution."""
    bot.opencode = fake_opencode_client
    fake_opencode_server.set_agent_message_response(
        "dr-gate",
        _json_response(
            {
                "effort": "deep",
                "needs_deep_confirmation": True,
                "suggested_user_confirmation": "Run deep research now?",
                "why": "broad report request",
            },
            "dr-gate",
        ),
    )

    update = build_message_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        text="deep research please",
        message_id=20,
        bot=fake_telegram_bot,
    )
    await bot._maybe_handle_deep_research(
        update=update,
        user_id=bot.settings.telegram_user_id,
        session_id="sess-cancel",
        text=update.effective_message.text or "",
    )

    token = next(iter(bot._research_pending.keys()))
    callback_update = build_callback_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        data=f"dr:cancel:{token}",
        message_id=21,
        bot=fake_telegram_bot,
    )
    handled = await bot._handle_research_callback(callback_update)

    assert handled is True
    assert bot._research_pending == {}
    assert len(fake_opencode_server.message_payloads["sess-cancel"]) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_malformed_stage_json_returns_controlled_failure_message(
    bot: JarvisBot,
    fake_opencode_client,
    fake_opencode_server: FakeOpenCodeServer,
    fake_telegram_bot: FakeTelegramBot,
) -> None:
    """Malformed JSON in one stage causes controlled deep-research failure response."""
    bot.opencode = fake_opencode_client
    _configure_research_stage_responses(fake_opencode_server)
    fake_opencode_server.set_agent_message_response(
        "dr-gate",
        _json_response(
            {
                "effort": "deep",
                "needs_deep_confirmation": True,
                "suggested_user_confirmation": "Run deep research now?",
                "why": "broad report request",
            },
            "dr-gate",
        ),
    )
    fake_opencode_server.set_agent_message_response(
        "dr-query-builder",
        _text_response("not-json", "dr-query-builder"),
    )

    update = build_message_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        text="deep research malformed",
        message_id=30,
        bot=fake_telegram_bot,
    )
    await bot._maybe_handle_deep_research(
        update=update,
        user_id=bot.settings.telegram_user_id,
        session_id="sess-fail",
        text=update.effective_message.text or "",
    )

    token = next(iter(bot._research_pending.keys()))
    callback_update = build_callback_update(
        user_id=bot.settings.telegram_user_id,
        chat_id=100,
        data=f"dr:confirm:{token}",
        message_id=31,
        bot=fake_telegram_bot,
    )
    await bot._handle_research_callback(callback_update)

    assert any(
        msg.text.startswith("Deep research failed:") for msg in fake_telegram_bot.sent_messages
    )
