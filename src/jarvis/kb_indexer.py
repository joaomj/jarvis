"""Knowledge-base indexer for saved markdown URLs."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from jarvis.database import Database
from jarvis.database.kb_storage_ops import KBChunkRow
from jarvis.kb_chunking import chunk_markdown
from jarvis.logging_config import get_logger

logger = get_logger(__name__)

FRONTMATTER_FENCE = "---"
FRONTMATTER_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")
TITLE_HEADING_RE = re.compile(r"^#{1,3}\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class KBIndexResult:
    """Result of one indexing run."""

    scanned_files: int
    indexed_files: int
    skipped_files: int
    failed_files: int


@dataclass(frozen=True)
class ParsedMarkdown:
    """Parsed markdown metadata/body."""

    metadata: dict[str, str]
    body: str


class KBIndexer:
    """Indexes markdown documents from `.jarvis/url-saves` into SQLite tables."""

    def __init__(self, db: Database, content_dir: str, chunk_size_chars: int) -> None:
        self._db = db
        self._content_dir = Path(content_dir)
        self._chunk_size_chars = chunk_size_chars
        self._last_scan_at: datetime | None = None

    def list_markdown_files(self) -> list[Path]:
        """Return sorted markdown files under configured KB directory."""
        if not self._content_dir.exists():
            return []
        return sorted(path for path in self._content_dir.rglob("*.md") if path.is_file())

    def index_all(self) -> KBIndexResult:
        """Scan and index all markdown files."""
        return self.index_paths(self.list_markdown_files())

    def index_paths(self, paths: list[Path]) -> KBIndexResult:
        """Index specific markdown files, continuing through partial failures."""
        indexed = 0
        skipped = 0
        failed = 0

        for path in paths:
            try:
                changed = self._index_file(path)
                if changed:
                    indexed += 1
                else:
                    skipped += 1
            except Exception as error:
                failed += 1
                self._db.log_ingest_error(str(path), str(error))
                logger.warning("kb_index_file_failed", path=str(path), error=str(error))

        self._last_scan_at = datetime.now(UTC)
        return KBIndexResult(
            scanned_files=len(paths),
            indexed_files=indexed,
            skipped_files=skipped,
            failed_files=failed,
        )

    def last_scan_age_seconds(self) -> float | None:
        """Return seconds since last full scan, if any."""
        if self._last_scan_at is None:
            return None
        return (datetime.now(UTC) - self._last_scan_at).total_seconds()

    def _index_file(self, path: Path) -> bool:
        content = path.read_text(encoding="utf-8")
        parsed = parse_markdown_document(content)
        body = parsed.body.strip()
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        storage_path = _storage_path(path)

        existing = self._db.get_document_by_path(storage_path)
        if existing and str(existing.get("content_hash", "")) == content_hash:
            return False

        url_original = parsed.metadata.get("url")
        title = parsed.metadata.get("title") or _fallback_title(body, path)
        document_id = self._db.upsert_document(
            markdown_path=storage_path,
            url_original=url_original,
            url_canonical=_canonicalize_url(url_original),
            title=title,
            domain=_extract_domain(url_original),
            captured_at=parsed.metadata.get("captured_at"),
            content_hash=content_hash,
            status="indexed",
            last_error=None,
        )

        chunks: list[KBChunkRow] = [
            KBChunkRow(
                chunk_index=chunk.chunk_index,
                heading=chunk.heading,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
                chunk_text=chunk.chunk_text,
            )
            for chunk in chunk_markdown(body, self._chunk_size_chars)
            if chunk.chunk_text
        ]
        self._db.replace_document_chunks(document_id, chunks)
        self._db.upsert_fts_for_document(document_id)
        return True


def parse_markdown_document(markdown: str) -> ParsedMarkdown:
    """Parse optional YAML-like frontmatter and markdown body."""
    if not markdown.startswith(f"{FRONTMATTER_FENCE}\n"):
        return ParsedMarkdown(metadata={}, body=markdown)

    lines = markdown.splitlines()
    if not lines or lines[0] != FRONTMATTER_FENCE:
        return ParsedMarkdown(metadata={}, body=markdown)

    closing_index: int | None = None
    for index in range(1, len(lines)):
        if lines[index].strip() == FRONTMATTER_FENCE:
            closing_index = index
            break

    if closing_index is None:
        return ParsedMarkdown(metadata={}, body=markdown)

    metadata: dict[str, str] = {}
    for line in lines[1:closing_index]:
        match = FRONTMATTER_LINE_RE.match(line.strip())
        if not match:
            continue
        key = match.group(1).lower()
        value = match.group(2).strip().strip('"').strip("'")
        metadata[key] = value

    body = "\n".join(lines[closing_index + 1 :])
    return ParsedMarkdown(metadata=metadata, body=body)


def _fallback_title(body: str, path: Path) -> str:
    heading_match = TITLE_HEADING_RE.search(body)
    if heading_match:
        return heading_match.group(1).strip()
    return path.stem


def _extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.netloc:
        return None
    return parsed.netloc.lower()


def _canonicalize_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        fragment="",
    )
    return urlunparse(normalized)


def _storage_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(resolved)
