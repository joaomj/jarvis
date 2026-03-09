"""X bookmarks synchronization.

Runs low-cost daily incremental sync and weekly full mirror reconcile.
Supports bookmark folders via X API.
"""

import json
from datetime import UTC, date, datetime
from typing import Any

from jarvis.bookmarks.client import DEFAULT_X_API_BASE_URL, DEFAULT_X_OAUTH_TOKEN_URL, XAPIClient
from jarvis.bookmarks.models import Bookmark
from jarvis.database import Database
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class BookmarkSync:
    """Bookmark synchronization manager."""

    def __init__(  # noqa: PLR0913
        self,
        db: Database,
        client_id: str,
        client_secret: str,
        base_url: str = DEFAULT_X_API_BASE_URL,
        oauth_token_url: str = DEFAULT_X_OAUTH_TOKEN_URL,
        api_timeout: float = 30.0,
        token_refresh_buffer_seconds: int = 300,
    ):
        """Initialize bookmark sync.

        Args:
            db: Database instance.
            client_id: OAuth 2.0 Client ID.
            client_secret: OAuth 2.0 Client Secret.
            base_url: X API base URL.
            oauth_token_url: OAuth 2.0 token endpoint URL.
            api_timeout: Request timeout in seconds.
            token_refresh_buffer_seconds: Seconds before expiry to refresh token.
        """
        self.db = db
        self.client = XAPIClient(
            db,
            client_id,
            client_secret,
            base_url=base_url,
            oauth_token_url=oauth_token_url,
            api_timeout=api_timeout,
            token_refresh_buffer_seconds=token_refresh_buffer_seconds,
        )

    async def sync_bookmarks(  # noqa: PLR0912
        self,
        full_sync: bool = False,
        sync_folders: bool = False,
    ) -> dict[str, Any]:
        """Sync bookmarks from X to local database.

        For full_sync=True, reconciles local DB to match remote state.
        Folder assignments can be synced separately to reduce API costs.

        Args:
            full_sync: If True, download ALL bookmarks (ignore since_id).
                     If False, only download new since last sync.
            sync_folders: If True, rebuild folder assignments from X folders.

        Returns:
            Dictionary with sync results.
        """
        # Atomic lock acquisition using conditional update
        if not self.db.acquire_sync_lock():
            logger.warning("sync_already_in_progress")
            return {"status": "skipped", "reason": "Sync already in progress"}

        try:
            existing_ids = self.db.get_all_bookmark_ids()
            sync_status = self.db.get_sync_status() or {}
            since_id = None if full_sync else sync_status.get("last_tweet_id")

            if full_sync:
                self.db.mark_all_bookmarks_unsynced()

            # Step 1: Fetch bookmarks (full or incremental)
            logger.info("fetching_all_bookmarks_full_data")
            all_bookmarks_list, last_tweet_id = await self.client.get_all_bookmarks(
                since_id=since_id,
            )
            all_bookmarks: dict[str, Bookmark] = {b.tweet_id: b for b in all_bookmarks_list}
            logger.info("all_bookmarks_fetched", count=len(all_bookmarks))

            # Step 2: Optionally fetch folder assignments (weekly)
            bookmark_folders: dict[str, set[str]] = {}  # tweet_id -> set of folder_ids
            folder_count = 0

            if sync_folders:
                logger.info("fetching_bookmark_folders")
                folders = await self.client.get_bookmark_folders()
                folder_count = len(folders)
                logger.info("folders_fetched", count=folder_count)

                for folder in folders:
                    self.db.save_folder(folder.folder_id, folder.folder_name)

                    logger.info(
                        "fetching_bookmark_ids_for_folder",
                        folder_id=folder.folder_id,
                        folder_name=folder.folder_name,
                    )
                    folder_tweet_ids = await self.client.get_all_folder_bookmark_ids(
                        folder_id=folder.folder_id,
                    )

                    for tweet_id in folder_tweet_ids:
                        if tweet_id not in bookmark_folders:
                            bookmark_folders[tweet_id] = set()
                        bookmark_folders[tweet_id].add(folder.folder_id)

                    logger.info(
                        "folder_bookmark_ids_fetched",
                        folder=folder.folder_name,
                        count=len(folder_tweet_ids),
                    )

            # Step 3: Save bookmarks and compute true new_count
            logger.info("saving_bookmarks", total=len(all_bookmarks))
            new_count = 0
            for tweet_id, bookmark in all_bookmarks.items():
                if tweet_id not in existing_ids:
                    new_count += 1

                self.db.save_bookmark(
                    tweet_id=bookmark.tweet_id,
                    author_username=bookmark.author.username,
                    author_name=bookmark.author.name,
                    author_verified=bookmark.author.verified,
                    text=bookmark.text,
                    note_text=bookmark.note_text,
                    created_at=bookmark.created_at.isoformat() if bookmark.created_at else None,
                    tweet_url=bookmark.tweet_url,
                    like_count=bookmark.metrics.like_count,
                    retweet_count=bookmark.metrics.retweet_count,
                    reply_count=bookmark.metrics.reply_count,
                    impression_count=bookmark.metrics.impression_count,
                    bookmark_count=bookmark.metrics.bookmark_count,
                    media_urls=json.dumps(bookmark.media_urls),
                    urls_expanded=json.dumps(bookmark.urls_expanded),
                    context_annotations=json.dumps(bookmark.context_annotations),
                    raw_json=json.dumps(bookmark.raw_json) if bookmark.raw_json else "{}",
                )

            # Step 4: Full mirror prune
            deleted_count = 0
            if full_sync:
                deleted_count = self.db.delete_unsynced_bookmarks()

            # Step 5: Optional folder rebuild
            if sync_folders:
                self.db.clear_all_folder_assignments()
                for tweet_id, folder_ids in bookmark_folders.items():
                    for folder_id in folder_ids:
                        self.db.assign_bookmark_to_folder(tweet_id, folder_id)

            # Step 6: Update sync status
            total_count = self.db.get_total_bookmarks_count()
            last_full_sync_date = date.today().isoformat() if full_sync else None
            last_folders_sync_date = date.today().isoformat() if sync_folders else None

            self.db.update_sync_status(
                last_tweet_id=last_tweet_id,
                last_full_sync_date=last_full_sync_date,
                last_folders_sync_date=last_folders_sync_date,
                total_bookmarks=total_count,
                sync_in_progress=False,
                first_sync_complete=True,
                last_sync_at=datetime.now(UTC).isoformat(),
            )

            logger.info(
                "sync_completed",
                new_bookmarks=new_count,
                total_bookmarks=total_count,
                deleted_bookmarks=deleted_count,
                folder_count=folder_count,
                full_sync=full_sync,
                folder_sync=sync_folders,
            )

            return {
                "status": "success",
                "new_bookmarks": new_count,
                "total_bookmarks": total_count,
                "deleted_bookmarks": deleted_count,
                "folder_count": folder_count,
                "full_sync": full_sync,
                "folder_sync": sync_folders,
            }

        except Exception as e:
            self.db.update_sync_status(sync_in_progress=False)
            logger.error("sync_failed", error=str(e), exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }
        finally:
            await self.client.close()
