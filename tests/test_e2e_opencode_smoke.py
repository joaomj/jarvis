"""Optional smoke tests against a real OpenCode server."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from jarvis.deep_research import DeepResearchOrchestrator
from jarvis.kb_prompting import build_grounded_prompt
from jarvis.kb_retrieval import RetrievedChunk
from jarvis.opencode_client import OpenCodeClient


def _is_enabled() -> bool:
    return os.getenv("JARVIS_ENABLE_E2E_OPENCODE") == "1"


@pytest.fixture
def e2e_client() -> OpenCodeClient:
    """Build real OpenCode client from environment variables."""
    if not _is_enabled():
        pytest.skip("Set JARVIS_ENABLE_E2E_OPENCODE=1 to run real OpenCode smoke tests")

    base_url = os.getenv("JARVIS_E2E_OPENCODE_URL")
    password = os.getenv("JARVIS_E2E_OPENCODE_PASSWORD")
    if not base_url or not password:
        pytest.skip("Missing JARVIS_E2E_OPENCODE_URL or JARVIS_E2E_OPENCODE_PASSWORD")

    return OpenCodeClient(base_url, password)


@pytest.mark.e2e_opencode
@pytest.mark.asyncio
async def test_e2e_memory_remember_recall_smoke(e2e_client: OpenCodeClient) -> None:
    """Smoke test memory-style remember/recall prompts against real OpenCode."""
    try:
        healthy, reason = await e2e_client.health_check()
        assert healthy, reason
        session_id = await e2e_client.create_session("jarvis-e2e-memory-smoke")

        remember_parts, _remember_info = await e2e_client.send_message(
            session_id,
            (
                "Classify this message for memory intent and return JSON only with keys "
                "action,payload,needs_confirmation,confirmation_question.\n"
                "Message: remember that Tocqueville emphasizes civil associations"
            ),
            agent="dr-gate",
        )
        recall_parts, _recall_info = await e2e_client.send_message(
            session_id,
            (
                "Classify this message for memory intent and return JSON only with keys "
                "action,payload,needs_confirmation,confirmation_question.\n"
                "Message: what do you recall about Tocqueville?"
            ),
            agent="dr-gate",
        )
    finally:
        await e2e_client.close()

    remember_text = "\n".join(p.get("text", "") for p in remember_parts if p.get("type") == "text")
    recall_text = "\n".join(p.get("text", "") for p in recall_parts if p.get("type") == "text")
    assert remember_text.strip()
    assert recall_text.strip()


@pytest.mark.e2e_opencode
@pytest.mark.asyncio
async def test_e2e_attachment_grounded_answer_smoke(e2e_client: OpenCodeClient) -> None:
    """Smoke test grounded answer prompt with citation format constraints."""
    chunk = RetrievedChunk(
        document_id=1,
        chunk_index=0,
        heading="Attachment",
        line_start=1,
        line_end=3,
        chunk_text="Federalist No. 10 argues that factions are inevitable and must be controlled.",
        title="Attachment note",
        url_original=None,
        markdown_path="vault/sources/attachments/indexed/fed10.md",
        score=-1.0,
    )
    prompt = build_grounded_prompt("What is the argument about factions?", [chunk])

    try:
        healthy, reason = await e2e_client.health_check()
        assert healthy, reason
        session_id = await e2e_client.create_session("jarvis-e2e-kb-smoke")
        parts, _info = await e2e_client.send_message(session_id, prompt)
    finally:
        await e2e_client.close()

    answer = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text")
    assert answer.strip()


@pytest.mark.e2e_opencode
@pytest.mark.asyncio
async def test_e2e_deep_research_confirmation_path_smoke(
    e2e_client: OpenCodeClient,
    tmp_path,
) -> None:
    """Smoke test deep research gate + run_job artifact generation path."""
    orchestrator = DeepResearchOrchestrator(str(tmp_path / "vault"))

    try:
        healthy, reason = await e2e_client.health_check()
        assert healthy, reason
        session_id = await e2e_client.create_session("jarvis-e2e-research-smoke")
        decision = await orchestrator.classify_request(
            opencode=e2e_client,
            session_id=session_id,
            question="Write a deep research report about democratic factions.",
        )
        assert decision.effort in {"quick", "sourced", "deep"}

        if decision.effort == "deep":
            result = await orchestrator.run_job(
                opencode=e2e_client,
                session_id=session_id,
                user_id=123,
                question="Write a deep research report about democratic factions.",
            )
            assert Path(result.report_path).exists()
    finally:
        await e2e_client.close()
