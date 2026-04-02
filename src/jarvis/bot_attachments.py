"""Attachment ingestion behavior for ``JarvisBot``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from telegram import Update

from jarvis.logging_config import get_logger

logger = get_logger(__name__)

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".rst", ".log"}


@dataclass(frozen=True)
class AttachmentIngestResult:
    """Result payload for one attachment ingestion."""

    raw_path: str
    markdown_path: str | None
    indexed: bool


class BotAttachmentsMixin:
    """Methods for ingesting Telegram attachments into the local vault."""

    async def _ingest_attachment_if_present(
        self,
        update: Update,
    ) -> AttachmentIngestResult | None:
        """Download and ingest one attached document if present."""
        message = update.effective_message
        if message is None or message.document is None or self.app is None:
            return None

        document = message.document
        file_name = document.file_name or f"attachment-{document.file_unique_id}"
        file_ext = Path(file_name).suffix.lower()
        captured_at = datetime.now(UTC)

        source_root = Path(self.settings.vault_root).expanduser() / "raw" / "attachments"
        day_path = captured_at.strftime("%Y/%m/%d")
        raw_dir = source_root / day_path
        md_dir = source_root / "indexed" / day_path
        raw_dir.mkdir(parents=True, exist_ok=True)
        md_dir.mkdir(parents=True, exist_ok=True)

        safe_stem = _sanitize_stem(Path(file_name).stem)
        unique = document.file_unique_id
        raw_path = raw_dir / f"{safe_stem}-{unique}{file_ext or '.bin'}"

        file_obj = await self.app.bot.get_file(document.file_id)
        data = await file_obj.download_as_bytearray()
        raw_path.write_bytes(bytes(data))

        markdown_path: Path | None = None
        indexed = False
        if self._is_text_attachment(document.mime_type, file_ext):
            text_content = bytes(data).decode("utf-8", errors="replace").strip()
            if text_content:
                markdown_path = md_dir / f"{safe_stem}-{unique}.md"
                markdown_path.write_text(
                    _render_attachment_markdown(
                        filename=file_name,
                        file_id=document.file_id,
                        captured_at=captured_at.isoformat(),
                        content=text_content,
                    ),
                    encoding="utf-8",
                )

                if self.kb_indexer is not None:
                    result = self.kb_indexer.index_paths([markdown_path])
                    indexed = result.indexed_files > 0 and result.failed_files == 0

        return AttachmentIngestResult(
            raw_path=str(raw_path),
            markdown_path=str(markdown_path) if markdown_path else None,
            indexed=indexed,
        )

    @staticmethod
    def _is_text_attachment(mime_type: str | None, file_ext: str) -> bool:
        """Return whether attachment is decodable text for indexing."""
        if mime_type and mime_type.startswith("text/"):
            return True
        return file_ext in TEXT_EXTENSIONS


def _sanitize_stem(stem: str) -> str:
    cleaned = [char.lower() if char.isalnum() else "-" for char in stem]
    normalized = "".join(cleaned).strip("-")
    return normalized or "attachment"


def _render_attachment_markdown(
    filename: str,
    file_id: str,
    captured_at: str,
    content: str,
) -> str:
    return (
        "---\n"
        "source_type: attachment\n"
        f"title: {filename}\n"
        f"file_id: {file_id}\n"
        f"captured_at: {captured_at}\n"
        "---\n\n"
        f"{content}\n"
    )
