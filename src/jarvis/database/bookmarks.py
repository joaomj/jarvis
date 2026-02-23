"""Bookmark storage and sync status operations."""

import sqlite3

from jarvis.database.core import DatabaseCore
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class BookmarkOperations(DatabaseCore):
    """X bookmark storage and synchronization status."""

    def save_bookmark(  # noqa: PLR0913
        self,
        tweet_id: str,
        author_username: str,
        author_name: str,
        author_verified: bool,
        text: str,
        note_text: str | None,
        created_at: str | None,
        tweet_url: str,
        like_count: int,
        retweet_count: int,
        reply_count: int,
        impression_count: int,
        bookmark_count: int,
        media_urls: str,
        urls_expanded: str,
        context_annotations: str,
        raw_json: str,
    ) -> None:
        """Save a bookmark to database.

        Args:
            tweet_id: Tweet ID.
            author_username: Author username.
            author_name: Author display name.
            author_verified: Author verified status.
            text: Tweet text.
            note_text: User's private note.
            created_at: Tweet creation timestamp.
            tweet_url: Tweet URL.
            like_count: Number of likes.
            retweet_count: Number of retweets.
            reply_count: Number of replies.
            impression_count: Number of impressions.
            bookmark_count: Number of bookmarks.
            media_urls: JSON string of media URLs.
            urls_expanded: JSON string of expanded URLs.
            context_annotations: JSON string of context annotations.
            raw_json: Raw API response JSON.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO x_bookmarks
                       (tweet_id, author_username, author_name, author_verified, text,
                        note_text, created_at, tweet_url, like_count, retweet_count,
                        reply_count, impression_count, bookmark_count, media_urls,
                        urls_expanded, context_annotations, raw_json, last_synced_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                       ON CONFLICT(tweet_id) DO UPDATE SET
                           author_username=excluded.author_username,
                           author_name=excluded.author_name,
                           author_verified=excluded.author_verified,
                           text=excluded.text,
                           note_text=excluded.note_text,
                           created_at=excluded.created_at,
                           tweet_url=excluded.tweet_url,
                           like_count=excluded.like_count,
                           retweet_count=excluded.retweet_count,
                           reply_count=excluded.reply_count,
                           impression_count=excluded.impression_count,
                           bookmark_count=excluded.bookmark_count,
                           media_urls=excluded.media_urls,
                           urls_expanded=excluded.urls_expanded,
                           context_annotations=excluded.context_annotations,
                           raw_json=excluded.raw_json,
                           last_synced_at=CURRENT_TIMESTAMP""",
                    (
                        tweet_id, author_username, author_name, author_verified, text,
                        note_text, created_at, tweet_url, like_count, retweet_count,
                        reply_count, impression_count, bookmark_count, media_urls,
                        urls_expanded, context_annotations, raw_json,
                    ),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "save_bookmark_failed",
                tweet_id=tweet_id,
                error=str(e),
            )

    def get_all_bookmark_ids(self) -> set[str]:
        """Get all bookmark tweet IDs.

        Returns:
            Set of tweet IDs currently stored in database.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT tweet_id FROM x_bookmarks")
                return {row[0] for row in cursor.fetchall()}
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("get_all_bookmark_ids_failed", error=str(e))
            return set()

    def get_total_bookmarks_count(self) -> int:
        """Get total distinct bookmark count in database.

        Returns:
            Distinct bookmark count.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(DISTINCT tweet_id) FROM x_bookmarks")
                row = cursor.fetchone()
                return int(row[0]) if row else 0
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("get_total_bookmarks_count_failed", error=str(e))
            return 0

    def mark_all_bookmarks_unsynced(self) -> None:
        """Mark all bookmarks as unsynced for full mirror reconciliation."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE x_bookmarks SET last_synced_at = NULL")
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("mark_all_bookmarks_unsynced_failed", error=str(e))

    def delete_unsynced_bookmarks(self) -> int:
        """Delete bookmarks not seen during current full reconciliation.

        Returns:
            Number of deleted rows.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM x_bookmarks WHERE last_synced_at IS NULL")
                return cursor.rowcount
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("delete_unsynced_bookmarks_failed", error=str(e))
            return 0

    def get_bookmarks_by_time_range(self, start_date: str, end_date: str) -> list[dict]:
        """Get bookmarks within time range.

        Args:
            start_date: Start date (ISO format or SQLite date function).
            end_date: End date (ISO format or SQLite date function).

        Returns:
            List of bookmark dictionaries.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT tweet_id, author_username, author_name, author_verified,
                              text, note_text, created_at, bookmarked_at, tweet_url,
                              like_count, retweet_count, reply_count, impression_count,
                              bookmark_count, media_urls, urls_expanded
                       FROM x_bookmarks
                       WHERE bookmarked_at >= ? AND bookmarked_at <= ?
                       ORDER BY bookmarked_at DESC""",
                    (start_date, end_date),
                )
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "get_bookmarks_by_time_range_failed",
                start_date=start_date,
                end_date=end_date,
                error=str(e),
            )
            return []

    def get_bookmark_by_id(self, tweet_id: str) -> dict | None:
        """Get a specific bookmark by tweet ID.

        Args:
            tweet_id: Tweet ID.

        Returns:
            Bookmark dictionary or None.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT tweet_id, author_username, author_name, author_verified,
                              text, note_text, created_at, bookmarked_at, tweet_url,
                              like_count, retweet_count, reply_count, impression_count,
                              bookmark_count, media_urls, urls_expanded, raw_json
                       FROM x_bookmarks
                       WHERE tweet_id = ?""",
                    (tweet_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row, strict=True))
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "get_bookmark_by_id_failed",
                tweet_id=tweet_id,
                error=str(e),
            )
            return None

    def get_sync_status(self) -> dict | None:
        """Get current sync status.

        Returns:
            Sync status dictionary or None.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT last_sync_date, last_sync_at, last_tweet_id,
                              last_full_sync_date, last_folders_sync_date,
                              total_bookmarks, sync_in_progress, first_sync_complete
                       FROM x_sync_status
                       WHERE id = 1""",
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row, strict=True))
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("get_sync_status_failed", error=str(e))
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
        """Update sync status.

        Args:
            last_sync_date: Last sync date string (YYYY-MM-DD).
            last_sync_at: Last sync timestamp.
            last_tweet_id: Last synced tweet ID.
            last_full_sync_date: Last full mirror sync date (YYYY-MM-DD).
            last_folders_sync_date: Last folder membership sync date (YYYY-MM-DD).
            total_bookmarks: Total bookmark count.
            sync_in_progress: Whether sync is in progress.
            first_sync_complete: Whether first full sync is complete.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                updates = []
                params = []
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
                    conn.execute(query, params)
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("update_sync_status_failed", error=str(e))

    def get_first_sync_status(self) -> bool:
        """Check if first full sync has been completed.

        Returns:
            bool: True if first sync complete.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT first_sync_complete FROM x_sync_status WHERE id = 1"
                )
                row = cursor.fetchone()
                return bool(row and row[0]) if row else False
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("get_first_sync_status_failed", error=str(e))
            return False

    def save_folder(self, folder_id: str, folder_name: str) -> None:
        """Save or update a bookmark folder.

        Args:
            folder_id: Folder ID from X API.
            folder_name: Folder name.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO x_bookmark_folders
                       (folder_id, folder_name)
                       VALUES (?, ?)""",
                    (folder_id, folder_name),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("save_folder_failed", folder_id=folder_id, error=str(e))

    def assign_bookmark_to_folder(self, tweet_id: str, folder_id: str) -> None:
        """Assign a bookmark to a folder.

        Args:
            tweet_id: Tweet ID.
            folder_id: Folder ID.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT OR IGNORE INTO x_bookmark_folder_assignments
                       (tweet_id, folder_id)
                       VALUES (?, ?)""",
                    (tweet_id, folder_id),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "assign_bookmark_to_folder_failed",
                tweet_id=tweet_id,
                folder_id=folder_id,
                error=str(e),
            )

    def clear_bookmark_folder_assignments(self, tweet_id: str) -> None:
        """Remove all folder assignments for a bookmark.

        Args:
            tweet_id: Tweet ID.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "DELETE FROM x_bookmark_folder_assignments WHERE tweet_id = ?",
                    (tweet_id,),
                )
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "clear_bookmark_folder_assignments_failed",
                tweet_id=tweet_id,
                error=str(e),
            )

    def get_folders_for_bookmark(self, tweet_id: str) -> list[dict]:
        """Get all folders assigned to a bookmark.

        Args:
            tweet_id: Tweet ID.

        Returns:
            List of folder dictionaries.
        """
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
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning(
                "get_folders_for_bookmark_failed",
                tweet_id=tweet_id,
                error=str(e),
            )
            return []

    def clear_all_folder_assignments(self) -> None:
        """Clear all folder assignments (used before full re-sync)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM x_bookmark_folder_assignments")
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("clear_all_folder_assignments_failed", error=str(e))
