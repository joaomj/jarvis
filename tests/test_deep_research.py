"""Tests for deep research orchestration and confirmation flow."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.bot import JarvisBot
from jarvis.config import Settings
from jarvis.deep_research import DeepResearchOrchestrator


@pytest.fixture
def settings(tmp_path):
    """Create test settings for deep research."""
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
    )


@pytest.mark.asyncio
async def test_deep_research_run_job_writes_artifacts(tmp_path) -> None:
    """Deep research job writes plan/sources/evidence/report/audit files."""
    orchestrator = DeepResearchOrchestrator(str(tmp_path / "vault"))

    async def fake_send_message(
        session_id: str,
        text: str,
        model: str | None = None,
        agent: str | None = None,
    ):
        payload_by_agent = {
            "dr-planner": {"sections": [{"id": "s1", "heading": "Intro"}]},
            "dr-query-builder": {"queries": ["history of factions"]},
            "dr-websearch-highrep": {
                "sources": [{"title": "Source", "url": "https://example.com"}]
            },
            "dr-source-triage": {"selected": [{"url_or_path": "https://example.com"}]},
            "dr-evidence-extractor": {"evidence_units": [{"evidence_id": "E1", "text": "quote"}]},
            "dr-citation-auditor": {"issues": [], "stats": {"uncited_claim_count": 0}},
        }
        if agent == "dr-section-writer":
            return ([{"type": "text", "text": "## Intro\nText [E1]."}], {})
        if agent == "dr-editor-integrator":
            return (
                [{"type": "text", "text": "# Report\nClaim [E1].\n\n## References\n- Source"}],
                {},
            )
        data = payload_by_agent.get(agent, {"ok": True})
        return ([{"type": "text", "text": json.dumps(data)}], {})

    opencode = MagicMock()
    opencode.send_message = AsyncMock(side_effect=fake_send_message)

    result = await orchestrator.run_job(
        opencode=opencode,
        session_id="sess-1",
        user_id=123,
        question="What are the strongest arguments about factions?",
    )

    assert result.report_path.endswith("report.md")
    assert result.audit_path is not None
    workspace = tmp_path / "vault" / "research" / result.job_id
    assert (workspace / "question.md").exists()
    assert (workspace / "plan.json").exists()
    assert (workspace / "sources.json").exists()
    assert (workspace / "evidence.json").exists()
    assert (workspace / "report.md").exists()
    assert (workspace / "audit.json").exists()


@pytest.mark.asyncio
async def test_deep_research_gate_requests_confirmation(settings) -> None:
    """Deep effort with confirmation flag creates pending confirmation entry."""
    bot = JarvisBot(settings)
    bot.model_selector = None

    bot.opencode = MagicMock()
    bot.opencode.send_message = AsyncMock(
        return_value=(
            [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "effort": "deep",
                            "needs_deep_confirmation": True,
                            "suggested_user_confirmation": "Run deep research now?",
                            "why": "broad report request",
                        }
                    ),
                }
            ],
            {},
        )
    )

    update = MagicMock()
    update.effective_message.reply_text = AsyncMock()

    handled = await bot._maybe_handle_deep_research(
        update=update,
        user_id=settings.telegram_user_id,
        session_id="sess-2",
        text="Please run deep research and write a 10-page report",
    )

    assert handled is True
    assert len(bot._research_pending) == 1
    update.effective_message.reply_text.assert_awaited_once()
