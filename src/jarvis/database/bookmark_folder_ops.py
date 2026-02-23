"""Bookmark folder assignment operations."""

from __future__ import annotations

import sqlite3

from jarvis.database.core import DatabaseCore
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class BookmarkFolderOperations(DatabaseCore):
    """Operations for bookmark folders and assignments."""

    def save_folder(self, folder_id: str, folder_name: str) -> None:
        """Save or update a bookmark folder."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO x_bookmark_folders
                       (folder_id, folder_name)
                       VALUES (?, ?)""",
                    (folder_id, folder_name),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("save_folder_failed", folder_id=folder_id, error=str(error))

    def assign_bookmark_to_folder(self, tweet_id: str, folder_id: str) -> None:
        """Assign a bookmark to a folder."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT OR IGNORE INTO x_bookmark_folder_assignments
                       (tweet_id, folder_id)
                       VALUES (?, ?)""",
                    (tweet_id, folder_id),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning(
                "assign_bookmark_to_folder_failed",
                tweet_id=tweet_id,
                folder_id=folder_id,
                error=str(error),
            )

    def clear_bookmark_folder_assignments(self, tweet_id: str) -> None:
        """Remove all folder assignments for a bookmark."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM x_bookmark_folder_assignments WHERE tweet_id = ?",
                    (tweet_id,),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning(
                "clear_bookmark_folder_assignments_failed",
                tweet_id=tweet_id,
                error=str(error),
            )

    def get_folders_for_bookmark(self, tweet_id: str) -> list[dict]:
        """Get all folders assigned to a bookmark."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT f.folder_id, f.folder_name
                       FROM x_bookmark_folders f
                       JOIN x_bookmark_folder_assignments a ON f.folder_id = a.folder_id
                       WHERE a.tweet_id = ?""",
                    (tweet_id,),
                )
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("get_folders_for_bookmark_failed", tweet_id=tweet_id, error=str(error))
            return []

    def clear_all_folder_assignments(self) -> None:
        """Clear all folder assignments (used before full re-sync)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM x_bookmark_folder_assignments")
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as error:
            logger.warning("clear_all_folder_assignments_failed", error=str(error))
