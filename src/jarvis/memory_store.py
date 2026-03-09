"""Vault-backed curated memory storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from jarvis.database import Database


@dataclass(frozen=True)
class MemoryRecord:
    """One curated memory entry."""

    memory_key: str
    content: str
    markdown_path: str
    created_at: str
    tags_csv: str


class MemoryStore:
    """Handles writing memory artifacts to vault and indexing metadata in SQLite."""

    def __init__(self, db: Database, vault_root: str) -> None:
        self._db = db
        self._vault_root = Path(vault_root).expanduser()
        self._memory_dir = self._vault_root / "memories"
        self._memory_dir.mkdir(parents=True, exist_ok=True)

    @property
    def memory_dir(self) -> Path:
        """Return memory directory path."""
        return self._memory_dir

    def add_memory(self, content: str, tags: list[str] | None = None) -> MemoryRecord:
        """Persist one memory entry to vault and SQLite."""
        normalized = content.strip()
        if not normalized:
            raise ValueError("memory content cannot be empty")

        now = datetime.now(UTC)
        memory_key = f"mem-{now.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
        tags_csv = ",".join(tag.strip() for tag in (tags or []) if tag.strip())
        markdown_path = self._memory_dir / f"{memory_key}.md"
        markdown_path.write_text(
            self._render_markdown(memory_key, now.isoformat(), normalized, tags_csv),
            encoding="utf-8",
        )
        self._db.create_memory_entry(
            memory_key=memory_key,
            content=normalized,
            markdown_path=str(markdown_path),
            tags_csv=tags_csv,
        )
        return MemoryRecord(
            memory_key=memory_key,
            content=normalized,
            markdown_path=str(markdown_path),
            created_at=now.isoformat(),
            tags_csv=tags_csv,
        )

    def search(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Search active memories and return typed records."""
        rows = self._db.search_active_memories(query=query, limit=limit)
        return [
            MemoryRecord(
                memory_key=str(row.get("memory_key", "")),
                content=str(row.get("content", "")),
                markdown_path=str(row.get("markdown_path", "")),
                created_at=str(row.get("created_at", "")),
                tags_csv=str(row.get("tags_csv", "")),
            )
            for row in rows
        ]

    def forget(self, query_or_key: str) -> MemoryRecord | None:
        """Forget one memory by key or latest matching query."""
        trimmed = query_or_key.strip()
        if not trimmed:
            return None

        by_key = self._db.get_memory_by_key(trimmed)
        if by_key and bool(by_key.get("active", 0)) and self._db.forget_memory_by_key(trimmed):
            return MemoryRecord(
                memory_key=str(by_key.get("memory_key", "")),
                content=str(by_key.get("content", "")),
                markdown_path=str(by_key.get("markdown_path", "")),
                created_at=str(by_key.get("created_at", "")),
                tags_csv=str(by_key.get("tags_csv", "")),
            )

        matched = self._db.forget_latest_matching_memory(trimmed)
        if matched is None:
            return None
        return MemoryRecord(
            memory_key=str(matched.get("memory_key", "")),
            content=str(matched.get("content", "")),
            markdown_path=str(matched.get("markdown_path", "")),
            created_at="",
            tags_csv="",
        )

    def list_recent(self, limit: int = 5) -> list[MemoryRecord]:
        """List active memories ordered by recency."""
        rows = self._db.list_recent_active_memories(limit=limit)
        return [
            MemoryRecord(
                memory_key=str(row.get("memory_key", "")),
                content=str(row.get("content", "")),
                markdown_path=str(row.get("markdown_path", "")),
                created_at=str(row.get("created_at", "")),
                tags_csv=str(row.get("tags_csv", "")),
            )
            for row in rows
        ]

    @staticmethod
    def _render_markdown(memory_key: str, created_at: str, content: str, tags_csv: str) -> str:
        quoted_tags = [f'"{tag}"' for tag in tags_csv.split(",") if tag]
        tags = f"[{', '.join(quoted_tags)}]" if quoted_tags else "[]"
        return (
            "---\n"
            f"memory_key: {memory_key}\n"
            f"created_at: {created_at}\n"
            f"tags: {tags}\n"
            "---\n\n"
            f"{content}\n"
        )
