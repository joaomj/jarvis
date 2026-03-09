"""Memory persistence operations."""

from __future__ import annotations

import sqlite3

from jarvis.database.core import DatabaseCore
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class MemoryOperations(DatabaseCore):
    """CRUD operations for curated memory entries."""

    def create_memory_entry(
        self,
        memory_key: str,
        content: str,
        markdown_path: str,
        tags_csv: str = "",
    ) -> int:
        """Insert a memory entry and return row id."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO memory_entries (memory_key, content, markdown_path, tags_csv)
                   VALUES (?, ?, ?, ?)""",
                (memory_key, content, markdown_path, tags_csv),
            )
            return int(cursor.lastrowid)

    def search_active_memories(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        """Search active memories by content/tags with LIKE matching."""
        safe_limit = max(1, min(limit, 20))
        like = f"%{query.strip()}%"
        if not query.strip():
            like = "%"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """SELECT id, memory_key, content, markdown_path, tags_csv, created_at
                   FROM memory_entries
                   WHERE active = 1 AND (content LIKE ? OR tags_csv LIKE ? OR memory_key LIKE ?)
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (like, like, like, safe_limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_memory_by_key(self, memory_key: str) -> dict[str, object] | None:
        """Get one memory row by key."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT id, memory_key, content, markdown_path, tags_csv, active, created_at, forgotten_at
                   FROM memory_entries
                   WHERE memory_key = ?""",
                (memory_key,),
            ).fetchone()
            return dict(row) if row else None

    def forget_memory_by_key(self, memory_key: str) -> bool:
        """Soft-delete one memory by key."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE memory_entries
                   SET active = 0, forgotten_at = CURRENT_TIMESTAMP
                   WHERE memory_key = ? AND active = 1""",
                (memory_key,),
            )
            return int(cursor.rowcount) > 0

    def forget_latest_matching_memory(self, query: str) -> dict[str, object] | None:
        """Forget the newest active memory matching a query and return it."""
        like = f"%{query.strip()}%"
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT id, memory_key, content, markdown_path
                   FROM memory_entries
                   WHERE active = 1 AND (content LIKE ? OR tags_csv LIKE ? OR memory_key LIKE ?)
                   ORDER BY created_at DESC
                   LIMIT 1""",
                (like, like, like),
            ).fetchone()
            if row is None:
                return None

            conn.execute(
                """UPDATE memory_entries
                   SET active = 0, forgotten_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (int(row["id"]),),
            )
            return dict(row)

    def list_recent_active_memories(self, limit: int = 5) -> list[dict[str, object]]:
        """Return most recent active memories."""
        safe_limit = max(1, min(limit, 20))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT id, memory_key, content, markdown_path, tags_csv, created_at
                   FROM memory_entries
                   WHERE active = 1
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (safe_limit,),
            ).fetchall()
            return [dict(row) for row in rows]
