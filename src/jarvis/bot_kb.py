"""Knowledge-base save intent behaviors for ``JarvisBot``."""

# mypy: ignore-errors

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from telegram import Update

from jarvis.bot_constants import KB_QUERY_KEYWORDS, SAVE_INTENT_KEYWORDS
from jarvis.kb_indexer import KBIndexer
from jarvis.kb_prompting import build_grounded_prompt, format_source_list
from jarvis.kb_retrieval import retrieve_chunks
from jarvis.logging_config import get_logger

logger = get_logger(__name__)

URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
CITATION_RE = re.compile(r"\[doc:\d+\s+chunk:\d+\]")


class BotKBMixin:
    """Methods for URL save intent routing and post-save indexing."""

    def _initialize_kb_state(self) -> None:
        default_dir = Path(
            getattr(self.settings, "database_path", ".jarvis/jarvis.db")
        ).expanduser()
        default_content_dir = default_dir.parent / "url-saves"
        content_dir = Path(getattr(self.settings, "kb_content_dir", str(default_content_dir)))
        content_dir.mkdir(parents=True, exist_ok=True)
        chunk_size_chars = int(getattr(self.settings, "kb_chunk_size_chars", 1800))
        self.kb_indexer = KBIndexer(
            db=self.db,
            content_dir=str(content_dir),
            chunk_size_chars=chunk_size_chars,
        )

    def _run_kb_startup_scan(self) -> None:
        if not self.kb_indexer:
            return
        result = self.kb_indexer.index_all()
        logger.info(
            "kb_startup_index_complete",
            scanned_files=result.scanned_files,
            indexed_files=result.indexed_files,
            skipped_files=result.skipped_files,
            failed_files=result.failed_files,
        )

    def _is_save_intent(self, text: str) -> bool:
        """Detect save/scrape intent from natural-language input."""
        candidate = text.strip()
        if not candidate or candidate.startswith(("!", "/")):
            return False

        urls = self._extract_urls(candidate)
        if not urls:
            return False
        if len(urls) == 1 and candidate == urls[0]:
            return True

        lowered = candidate.lower()
        return any(keyword in lowered for keyword in SAVE_INTENT_KEYWORDS)

    def _is_kb_answer_intent(self, text: str) -> bool:
        """Detect when user asks for answer grounded in saved KB content."""
        lowered = text.strip().lower()
        if not lowered:
            return False
        return any(keyword in lowered for keyword in KB_QUERY_KEYWORDS)

    def _extract_urls(self, text: str) -> list[str]:
        return URL_RE.findall(text)

    async def _handle_save_intent(
        self, update: Update, user_id: int, session_id: str, text: str
    ) -> bool:
        """Delegate URL save flow to OpenCode and register completion callback."""
        message = update.effective_message
        if not message or not self.opencode:
            return False

        if self.events.has_pending_prompt(session_id):
            await self._send_feedback_message(
                update,
                user_id,
                "I am still processing your previous request. Please wait for completion.",
                source="status",
                prompt_text=text,
            )
            return True

        urls = self._extract_urls(text)
        if not urls:
            return False

        selected_model = None
        if self.model_selector:
            selected_model = self.model_selector.get_model_for_user(user_id)

        known_paths: tuple[str, ...] = ()
        if self.kb_indexer:
            known_paths = tuple(
                str(path.resolve()) for path in self.kb_indexer.list_markdown_files()
            )

        await self.opencode.prompt_async(
            session_id,
            self._build_save_prompt(text, urls),
            model=selected_model,
        )
        self.events.register_pending_prompt(
            session_id=session_id,
            user_id=user_id,
            chat_id=message.chat_id,
            in_message_id=message.message_id,
            prompt_text=text,
            session_title=f"jarvis-session-{session_id[:8]}",
            kind="save",
            known_markdown_paths=known_paths,
        )
        await self._send_feedback_message(
            update,
            user_id,
            "Saving this now... I will confirm when it is indexed.",
            source="status",
            prompt_text=text,
        )
        return True

    async def _on_save_completed(self, pending: Any) -> None:
        """Refresh KB index after a save completion event and notify user."""
        if not self.kb_indexer or not self.app:
            return

        previous = set(getattr(pending, "known_markdown_paths", ()))
        current_paths = self.kb_indexer.list_markdown_files()
        new_paths = [path for path in current_paths if str(path.resolve()) not in previous]

        result = (
            self.kb_indexer.index_paths(new_paths) if new_paths else self.kb_indexer.index_all()
        )
        confirmation = (
            "Save complete. "
            f"Indexed {result.indexed_files}, skipped {result.skipped_files}, failed {result.failed_files}."
        )
        await self.app.bot.send_message(chat_id=pending.chat_id, text=confirmation)

    async def _handle_kb_answer_intent(
        self,
        user_id: int,
        session_id: str,
        text: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Retrieve KB context and request a grounded cited answer."""
        if not self.kb_indexer or not self.opencode:
            return self._insufficient_evidence_result()

        self._refresh_kb_index_if_stale()

        max_chunks = int(getattr(self.settings, "kb_max_chunks_per_query", 6))
        chunks = retrieve_chunks(self.db, text, limit=max_chunks)
        if not chunks:
            return self._insufficient_evidence_result()

        selected_model = None
        if self.model_selector:
            selected_model = self.model_selector.get_model_for_user(user_id)

        prompt = build_grounded_prompt(text, chunks)
        parts, info = await self.opencode.send_message(session_id, prompt, model=selected_model)
        answer_text = "\n".join(
            part.get("text", "") for part in parts if part.get("type") == "text"
        ).strip()
        if not answer_text or not CITATION_RE.search(answer_text):
            logger.warning("kb_answer_missing_citations", session_id=session_id)
            return self._insufficient_evidence_result()

        sources = format_source_list(chunks)
        final_text = f"{answer_text}\n\nSources:\n{sources}" if sources else answer_text
        return ([{"type": "text", "text": final_text}], info)

    def _refresh_kb_index_if_stale(self) -> None:
        if not self.kb_indexer:
            return
        stale_seconds = int(getattr(self.settings, "kb_rescan_stale_seconds", 300))
        age_seconds = self.kb_indexer.last_scan_age_seconds()
        if age_seconds is not None and age_seconds <= stale_seconds:
            return
        result = self.kb_indexer.index_all()
        logger.info(
            "kb_rescan_complete",
            scanned_files=result.scanned_files,
            indexed_files=result.indexed_files,
            skipped_files=result.skipped_files,
            failed_files=result.failed_files,
        )

    def _insufficient_evidence_result(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        text = (
            "I do not have enough evidence in your saved articles to answer that confidently. "
            "Try saving more sources or narrowing the question."
        )
        return (
            [{"type": "text", "text": text}],
            {"providerID": "jarvis", "modelID": "kb-local", "agent": "kb"},
        )

    def _build_save_prompt(self, original_text: str, urls: list[str]) -> str:
        urls_text = "\n".join(f"- {url}" for url in urls)
        return (
            "Scrape this URL and save it as markdown for my local knowledge base.\n"
            "Use the existing firecrawl scraping workflow.\n"
            "Write files under .jarvis/url-saves/.\n"
            "Use YAML frontmatter with: url, title, captured_at (and author/published/description when available).\n"
            f"User request: {original_text}\n"
            f"URLs:\n{urls_text}"
        )
