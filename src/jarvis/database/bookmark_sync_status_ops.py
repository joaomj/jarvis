"""Bookmark synchronization status operations."""

from __future__ import annotations

import sqlite3

from jarvis.database.core import DatabaseCore
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class BookmarkSyncStatusOperations(DatabaseCore):
    """Operations for x_sync_status metadata."""

    def get_sync_status(self) -> dict | None:
        """Get current sync status."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT last_sync_date, last_sync_at, last_tweet_id,
                              last_full_sync_date, last_folders_sync_date,
                              total_bookmarks, sync_in_progress, first_sync_complete
                       FROM x_sync_status
                       WHERE id = 1"""
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row, strict=True))
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("get_sync_status_failed", error=str(error))
            return None

    def update_sync_status(  # noqa: PLR0913
        self,
        last_sync_date: str | None = None,
        last_sync_at: str | None = None,
        last_tweet_id: str | None = None,
        last_full_sync_date: str | None = None,
        last_folders_sync_date: str | None = None,
        total_bookmarks: int | None = None,
        sync_in_progress: bool | None = None,
        first_sync_complete: bool | None = None,
    ) -> None:
        """Update sync status fields that were provided."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                updates: list[str] = []
                params: list[str | int] = []
                if last_sync_date is not None:
                    updates.append("last_sync_date = ?")
                    params.append(last_sync_date)
                if last_sync_at is not None:
                    updates.append("last_sync_at = ?")
                    params.append(last_sync_at)
                if last_tweet_id is not None:
                    updates.append("last_tweet_id = ?")
                    params.append(last_tweet_id)
                if last_full_sync_date is not None:
                    updates.append("last_full_sync_date = ?")
                    params.append(last_full_sync_date)
                if last_folders_sync_date is not None:
                    updates.append("last_folders_sync_date = ?")
                    params.append(last_folders_sync_date)
                if total_bookmarks is not None:
                    updates.append("total_bookmarks = ?")
                    params.append(total_bookmarks)
                if sync_in_progress is not None:
                    updates.append("sync_in_progress = ?")
                    params.append(1 if sync_in_progress else 0)
                if first_sync_complete is not None:
                    updates.append("first_sync_complete = ?")
                    params.append(1 if first_sync_complete else 0)

                if updates:
                    query = f"UPDATE x_sync_status SET {', '.join(updates)} WHERE id = 1"  # noqa: S608
                    conn.execute(query, tuple(params))
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("update_sync_status_failed", error=str(error))

    def get_first_sync_status(self) -> bool:
        """Check if first full sync has been completed."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT first_sync_complete FROM x_sync_status WHERE id = 1")
                row = cursor.fetchone()
                return bool(row and row[0]) if row else False
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("get_first_sync_status_failed", error=str(error))
            return False
