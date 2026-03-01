"""Deep research orchestration using OpenCode subagents."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field


class _OpenCodeLike(Protocol):
    async def send_message(
        self,
        session_id: str,
        text: str,
        model: str | None = None,
        agent: str | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]: ...


class _ModelSelectorLike(Protocol):
    def get_model_for_user(self, user_id: int) -> str | None: ...


class DeepResearchDecision(BaseModel):
    """Decision payload from dr-gate."""

    effort: Literal["quick", "sourced", "deep"] = Field(default="quick")
    needs_deep_confirmation: bool = Field(default=False)
    suggested_user_confirmation: str | None = Field(default=None)
    why: str = Field(default="")


class DeepResearchJobResult(BaseModel):
    """Deep research output metadata."""

    job_id: str
    workspace_path: str
    report_path: str
    audit_path: str | None = None


class DeepResearchOrchestrator:
    """Runs staged deep research jobs and writes local artifacts."""

    def __init__(self, vault_root: str) -> None:
        self._vault_root = Path(vault_root).expanduser()
        self._research_root = self._vault_root / "research"
        self._research_root.mkdir(parents=True, exist_ok=True)

    async def classify_request(
        self,
        opencode: _OpenCodeLike,
        session_id: str,
        question: str,
        model: str | None = None,
    ) -> DeepResearchDecision:
        """Classify request effort via dr-gate agent."""
        gate_prompt = (
            "Classify this request effort into quick|sourced|deep and return JSON only with keys: "
            "effort, needs_deep_confirmation, suggested_user_confirmation, why.\n"
            f"Question: {question}"
        )
        parts, _info = await opencode.send_message(
            session_id,
            gate_prompt,
            model=model,
            agent="dr-gate",
        )
        text = _merge_text(parts)
        payload = _extract_json_dict(text)
        if payload is None:
            return DeepResearchDecision(
                effort="quick",
                needs_deep_confirmation=False,
                suggested_user_confirmation=None,
                why="gate_parse_failed",
            )
        try:
            return DeepResearchDecision.model_validate(payload)
        except Exception:
            return DeepResearchDecision(
                effort="quick",
                needs_deep_confirmation=False,
                suggested_user_confirmation=None,
                why="gate_validation_failed",
            )

    async def run_job(
        self,
        opencode: _OpenCodeLike,
        session_id: str,
        user_id: int,
        question: str,
        model: str | None = None,
    ) -> DeepResearchJobResult:
        """Run staged deep research workflow and persist artifacts."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        job_id = f"dr-{timestamp}-{uuid4().hex[:8]}"
        workspace = self._research_root / job_id
        workspace.mkdir(parents=True, exist_ok=True)

        question_path = workspace / "question.md"
        question_path.write_text(
            f"# Deep Research Question\n\n- user_id: {user_id}\n- created_at: {datetime.now(UTC).isoformat()}\n\n{question}\n",
            encoding="utf-8",
        )

        plan = await self._run_json_stage(
            opencode,
            session_id,
            model,
            agent="dr-planner",
            prompt=(
                "Create a deep research plan for this question. Return JSON only.\n"
                f"Question: {question}"
            ),
        )
        _write_json(workspace / "plan.json", plan)

        queries = await self._run_json_stage(
            opencode,
            session_id,
            model,
            agent="dr-query-builder",
            prompt=(
                "Generate web-search queries from this plan. Return JSON only.\n"
                f"Plan JSON:\n{json.dumps(plan, ensure_ascii=True)}"
            ),
        )
        _write_json(workspace / "queries.json", queries)

        web_sources = await self._run_json_stage(
            opencode,
            session_id,
            model,
            agent="dr-websearch-highrep",
            prompt=(
                "Find high-reputation sources for this question and query set. Return JSON only.\n"
                f"Question: {question}\n"
                f"Queries JSON:\n{json.dumps(queries, ensure_ascii=True)}"
            ),
        )
        _write_json(workspace / "sources.json", web_sources)

        triaged = await self._run_json_stage(
            opencode,
            session_id,
            model,
            agent="dr-source-triage",
            prompt=(
                "Rank and triage these sources for the report. Return JSON only.\n"
                f"Sources JSON:\n{json.dumps(web_sources, ensure_ascii=True)}"
            ),
        )
        _write_json(workspace / "triage.json", triaged)

        evidence = await self._run_json_stage(
            opencode,
            session_id,
            model,
            agent="dr-evidence-extractor",
            prompt=(
                "Extract evidence units from selected sources. Return JSON only.\n"
                f"Selected sources JSON:\n{json.dumps(triaged, ensure_ascii=True)}"
            ),
        )
        _write_json(workspace / "evidence.json", evidence)

        section_markdown = await self._run_markdown_stage(
            opencode,
            session_id,
            model,
            agent="dr-section-writer",
            prompt=(
                "Draft one strong body section from this evidence. Use inline evidence IDs.\n"
                f"Evidence JSON:\n{json.dumps(evidence, ensure_ascii=True)}"
            ),
        )
        (workspace / "section.md").write_text(section_markdown, encoding="utf-8")

        report_markdown = await self._run_markdown_stage(
            opencode,
            session_id,
            model,
            agent="dr-editor-integrator",
            prompt=(
                "Integrate into an academic-style report with references.\n"
                f"Plan JSON:\n{json.dumps(plan, ensure_ascii=True)}\n\n"
                f"Section draft:\n{section_markdown}\n\n"
                f"Evidence JSON:\n{json.dumps(evidence, ensure_ascii=True)}"
            ),
        )
        report_path = workspace / "report.md"
        report_path.write_text(report_markdown, encoding="utf-8")

        audit = await self._run_json_stage(
            opencode,
            session_id,
            model,
            agent="dr-citation-auditor",
            prompt=(
                "Audit this report for citation completeness. Return JSON only.\n"
                f"Report:\n{report_markdown}\n\n"
                f"Evidence JSON:\n{json.dumps(evidence, ensure_ascii=True)}"
            ),
        )
        audit_path = workspace / "audit.json"
        _write_json(audit_path, audit)

        return DeepResearchJobResult(
            job_id=job_id,
            workspace_path=str(workspace),
            report_path=str(report_path),
            audit_path=str(audit_path),
        )

    async def _run_json_stage(
        self,
        opencode: _OpenCodeLike,
        session_id: str,
        model: str | None,
        *,
        agent: str,
        prompt: str,
    ) -> dict[str, Any]:
        parts, _info = await opencode.send_message(session_id, prompt, model=model, agent=agent)
        payload = _extract_json_dict(_merge_text(parts))
        return payload if payload is not None else {"raw": _merge_text(parts), "agent": agent}

    async def _run_markdown_stage(
        self,
        opencode: _OpenCodeLike,
        session_id: str,
        model: str | None,
        *,
        agent: str,
        prompt: str,
    ) -> str:
        parts, _info = await opencode.send_message(session_id, prompt, model=model, agent=agent)
        return _merge_text(parts).strip()


def _merge_text(parts: list[dict[str, Any]]) -> str:
    return "\n".join(part.get("text", "") for part in parts if part.get("type") == "text").strip()


def _extract_json_dict(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    candidates = [stripped]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and start < end:
        candidates.append(stripped[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
