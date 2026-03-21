"""Web fallback answer helpers for grounded KB responses."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

WEB_CITATION_RE = re.compile(r"\[web:\d+\]")


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


async def build_web_fallback_answer(
    opencode: _OpenCodeLike,
    model_selector: _ModelSelectorLike | None,
    user_id: int,
    session_id: str,
    question: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Return sourced web answer tuple or None when insufficient."""
    selected_model = model_selector.get_model_for_user(user_id) if model_selector else None

    discovery_prompt = (
        "Find high-reputation web sources for this question and return JSON only with key 'sources'.\n"
        "Each source item must include: title, url, why_relevant.\n"
        f"Question: {question}"
    )
    source_parts, _source_info = await opencode.send_message(
        session_id,
        discovery_prompt,
        model=selected_model,
        agent="web-search",
    )
    source_text = "\n".join(
        part.get("text", "") for part in source_parts if part.get("type") == "text"
    ).strip()
    source_payload = _extract_json_payload(source_text)
    sources = source_payload.get("sources") if source_payload else None
    if not isinstance(sources, list) or not sources:
        return None

    synthesis_prompt = (
        "Answer the question using only these sources.\n"
        "Use inline citations in format [web:1], [web:2], etc.\n"
        "If evidence is weak, say so.\n"
        f"Question: {question}\n"
        f"Sources JSON:\n{json.dumps(sources, ensure_ascii=True)}"
    )
    answer_parts, answer_info = await opencode.send_message(
        session_id,
        synthesis_prompt,
        model=selected_model,
        agent="synthesizer",
    )
    answer_text = "\n".join(
        part.get("text", "") for part in answer_parts if part.get("type") == "text"
    ).strip()
    if not answer_text or not WEB_CITATION_RE.search(answer_text):
        return None

    source_lines: list[str] = []
    for idx, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            continue
        title = str(source.get("title", "Source"))
        url = str(source.get("url", ""))
        source_lines.append(f"[web:{idx}] {title} - {url}")

    final_text = answer_text
    if source_lines:
        final_text = f"{answer_text}\n\nSources:\n" + "\n".join(source_lines)
    return ([{"type": "text", "text": final_text}], answer_info)


def _extract_json_payload(text: str) -> dict[str, object] | None:
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
