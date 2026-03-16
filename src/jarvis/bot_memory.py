"""Memory and private-mode behaviors for ``JarvisBot``."""

from __future__ import annotations

import json
import re

from telegram import Update

from jarvis.logging_config import get_logger
from jarvis.memory_store import MemoryStore

logger = get_logger(__name__)

PRIVATE_PREFIX_RE = re.compile(r"^(?:<private>\s*|private:\s*|\/private\s+)", re.IGNORECASE)
MEMORY_SNIPPET_MAX_CHARS = 160
ELLIPSIS_CHARS = 3


class BotMemoryMixin:
    """Methods for curated memory and private turns."""

    def _initialize_memory_state(self) -> None:
        """Initialize vault-backed memory store."""
        self.memory_store = MemoryStore(self.db, self.settings.vault_root)

    def _is_private_intent(self, text: str) -> bool:
        """Detect private-turn prefix markers."""
        return bool(PRIVATE_PREFIX_RE.match(text.strip()))

    def _strip_private_marker(self, text: str) -> str:
        """Remove private prefix marker from user text."""
        return PRIVATE_PREFIX_RE.sub("", text.strip(), count=1).strip()

    async def _handle_memory_intent(  # noqa: PLR0911, PLR0912
        self,
        update: Update,
        user_id: int,
        session_id: str,
        text: str,
    ) -> bool:
        """Handle remember/forget/recall intents locally."""
        if self.memory_store is None or self.opencode is None:
            return False

        try:
            decision = await self._classify_memory_intent(user_id, session_id, text)
        except Exception as error:
            logger.warning("memory_intent_classification_failed", error=str(error))
            return False
        action = decision.get("action", "none")
        payload = str(decision.get("payload", "")).strip()
        if action == "none":
            return False

        if bool(decision.get("needs_confirmation", False)):
            prompt = str(decision.get("confirmation_question", "")).strip()
            if not prompt:
                prompt = (
                    "I am not fully sure this is a memory action. Please clarify what to remember."
                )
            await self._send_feedback_message(
                update,
                user_id,
                prompt,
                source="memory",
                prompt_text=text,
            )
            return True

        if action == "remember":
            raw_content = payload
            if not raw_content:
                await self._send_feedback_message(
                    update,
                    user_id,
                    "Please provide something to remember.",
                    source="memory",
                    prompt_text=text,
                )
                return True

            record = self.memory_store.add_memory(raw_content)
            await self._send_feedback_message(
                update,
                user_id,
                (f"Saved to memory.\nKey: `{record.memory_key}`\nPath: `{record.markdown_path}`"),
                source="memory",
                prompt_text=text,
                parse_mode="MarkdownV2",
            )
            return True

        if action == "forget":
            target = payload
            forgotten = self.memory_store.forget(target)
            response = (
                f"Forgot memory `{forgotten.memory_key}`."
                if forgotten
                else "I could not find an active memory matching that request."
            )
            await self._send_feedback_message(
                update,
                user_id,
                response,
                source="memory",
                prompt_text=text,
                parse_mode="MarkdownV2",
            )
            return True

        if action == "recall":
            query = payload
            records = self.memory_store.search(query=query or "", limit=5)
            if not records:
                response = "I do not have active memories matching that yet."
            else:
                lines = ["Here is what I remember:"]
                for index, record in enumerate(records, start=1):
                    snippet = record.content.strip().replace("\n", " ")
                    if len(snippet) > MEMORY_SNIPPET_MAX_CHARS:
                        trimmed_length = MEMORY_SNIPPET_MAX_CHARS - ELLIPSIS_CHARS
                        snippet = f"{snippet[:trimmed_length]}..."
                    lines.append(f"{index}. [{record.memory_key}] {snippet}")
                response = "\n".join(lines)

            await self._send_feedback_message(
                update,
                user_id,
                response,
                source="memory",
                prompt_text=text,
            )
            return True

        return False

    async def _classify_memory_intent(
        self,
        user_id: int,
        session_id: str,
        text: str,
    ) -> dict[str, object]:
        """Classify memory action using model understanding."""
        selected_model = (
            self.model_selector.get_model_for_user(user_id) if self.model_selector else None
        )
        prompt = (
            "Classify whether this message asks to manage personal memory. Return JSON only with keys: "
            "action, payload, needs_confirmation, confirmation_question.\n"
            "Valid actions: remember, forget, recall, none.\n"
            f"Message: {text}"
        )
        parts, _info = await self.opencode.send_message(
            session_id,
            prompt,
            model=selected_model,
            agent="classifier",
        )
        combined = "\n".join(part.get("text", "") for part in parts if part.get("type") == "text")
        parsed = _extract_json_payload(combined)
        if not parsed:
            return {"action": "none", "payload": "", "needs_confirmation": False}
        return parsed


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
