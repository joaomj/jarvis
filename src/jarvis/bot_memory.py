"""Memory and private-mode behaviors for ``JarvisBot``."""

from __future__ import annotations

import re

from telegram import Update

from jarvis.logging_config import get_logger
from jarvis.memory_store import MemoryStore

logger = get_logger(__name__)

REMEMBER_RE = re.compile(r"^(?:remember|memorize|note that)\s+(.+)$", re.IGNORECASE)
FORGET_RE = re.compile(r"^(?:forget|remove memory|delete memory)\s+(.+)$", re.IGNORECASE)
RECALL_RE = re.compile(
    r"^(?:what do you remember(?: about)?|recall|from memory)\s*(.*)$",
    re.IGNORECASE,
)
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

    async def _handle_memory_intent(self, update: Update, user_id: int, text: str) -> bool:
        """Handle remember/forget/recall intents locally."""
        if self.memory_store is None:
            return False

        candidate = text.strip()
        remember_match = REMEMBER_RE.match(candidate)
        if remember_match:
            raw_content = remember_match.group(1).strip()
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

        forget_match = FORGET_RE.match(candidate)
        if forget_match:
            target = forget_match.group(1).strip()
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

        recall_match = RECALL_RE.match(candidate)
        if recall_match:
            query = recall_match.group(1).strip()
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
