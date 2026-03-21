"""Core database functionality - connection and schema initialization."""

import sqlite3
from pathlib import Path

from jarvis.database.schema_sql import SCHEMA
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseCore:
    """Core database connection and schema management."""

    db_path: Path
    _message_content_max_length: int
    _response_cleanup_days: int

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(SCHEMA)
            self._migrate_sync_status_columns(conn)
            self._migrate_memory_columns(conn)

    def _migrate_sync_status_columns(self, conn: sqlite3.Connection) -> None:
        """Backfill newer x_sync_status columns for existing databases."""
        cursor = conn.execute("PRAGMA table_info(x_sync_status)")
        column_names = {row[1] for row in cursor.fetchall()}

        if "last_full_sync_date" not in column_names:
            conn.execute("ALTER TABLE x_sync_status ADD COLUMN last_full_sync_date TEXT")

        if "last_folders_sync_date" not in column_names:
            conn.execute("ALTER TABLE x_sync_status ADD COLUMN last_folders_sync_date TEXT")

    def _migrate_memory_columns(self, conn: sqlite3.Connection) -> None:
        """Backfill newer memory columns for existing databases."""
        cursor = conn.execute("PRAGMA table_info(memory_entries)")
        column_names = {str(row[1]) for row in cursor.fetchall()}

        if "title" not in column_names:
            conn.execute("ALTER TABLE memory_entries ADD COLUMN title TEXT")
        if "memory_type" not in column_names:
            conn.execute("ALTER TABLE memory_entries ADD COLUMN memory_type TEXT DEFAULT 'fact'")
        if "importance" not in column_names:
            conn.execute("ALTER TABLE memory_entries ADD COLUMN importance REAL DEFAULT 0.5")
        if "strength" not in column_names:
            conn.execute("ALTER TABLE memory_entries ADD COLUMN strength REAL DEFAULT 1.0")
        if "access_count" not in column_names:
            conn.execute("ALTER TABLE memory_entries ADD COLUMN access_count INTEGER DEFAULT 0")
        if "is_permanent" not in column_names:
            conn.execute("ALTER TABLE memory_entries ADD COLUMN is_permanent INTEGER DEFAULT 0")
        if "last_accessed" not in column_names:
            conn.execute("ALTER TABLE memory_entries ADD COLUMN last_accessed TIMESTAMP")

        conn.execute(
            "UPDATE memory_entries SET title = COALESCE(title, memory_key) WHERE title IS NULL"
        )

    def _execute(
        self,
        query: str,
        params: tuple = (),
        *,
        fetch: bool = False,
    ) -> list | None:
        """Execute a query with error handling.

        Args:
            query: SQL query.
            params: Query parameters.
            fetch: Whether to fetch and return results.

        Returns:
            List of rows if fetch=True, None otherwise.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            if fetch:
                cursor = conn.execute(query, params)
                return cursor.fetchall()
            conn.execute(query, params)
            return None

    def _execute_dict(
        self,
        query: str,
        params: tuple = (),
    ) -> list[dict]:
        """Execute a query and return results as list of dicts.

        Args:
            query: SQL query.
            params: Query parameters.

        Returns:
            List of dictionaries with column names as keys.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
