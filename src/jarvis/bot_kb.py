"""Knowledge-base behaviors for ``JarvisBot``."""

# mypy: ignore-errors

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from jarvis.kb_indexer import KBIndexer
from jarvis.logging_config import get_logger

logger = get_logger(__name__)

URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)


class BotKBMixin:
    """Methods for knowledge base indexing and management."""

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
            context_store=self.context_store,
        )

    def _run_kb_startup_scan(self) -> None:
        """Run KB startup scan synchronously."""
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

    async def _run_kb_startup_scan_async(self) -> None:
        """Run KB startup scan asynchronously to avoid blocking."""
        if not self.kb_indexer:
            return
        try:
            result = await asyncio.to_thread(self.kb_indexer.index_all)
            logger.info(
                "kb_startup_index_complete",
                scanned_files=result.scanned_files,
                indexed_files=result.indexed_files,
                skipped_files=result.skipped_files,
                failed_files=result.failed_files,
            )
        except Exception as e:
            logger.error("kb_startup_scan_failed", error=str(e))

    def _extract_urls(self, text: str) -> list[str]:
        return URL_RE.findall(text)

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
