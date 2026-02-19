"""Scheduled sync for X bookmarks.

Handles full sync on first run, incremental sync thereafter.
Supports bookmark folders via X API.
"""

import json
from typing import Any

from jarvis.bookmarks.client import XAPIClient
from jarvis.bookmarks.models import Bookmark
from jarvis.database import Database
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class BookmarkSync:
    """Bookmark synchronization manager."""

    def __init__(
        self,
        db: Database,
        client_id: str,
        client_secret: str,
        base_url: str = "https://api.twitter.com/2",
        oauth_token_url: str = "https://api.x.com/2/oauth2/token",
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

    async def sync_bookmarks(self, full_sync: bool = False) -> dict[str, Any]:
        """Sync bookmarks from X to local database.

        Fetches bookmarks per-folder to capture folder assignments.
        For full_sync=True, clears existing folder assignments first.

        Args:
            full_sync: If True, download ALL bookmarks (ignore since_id).
                     If False, only download new since last sync.

        Returns:
            Dictionary with sync results.
        """
        sync_status = self.db.get_sync_status()

        if sync_status and sync_status.get("sync_in_progress"):
            logger.warning("sync_already_in_progress")
            return {"status": "skipped", "reason": "Sync already in progress"}

        self.db.update_sync_status(sync_in_progress=True)

        try:
            # For full sync, clear existing folder assignments
            if full_sync:
                logger.info("clearing_folder_assignments_for_full_sync")
                self.db.clear_all_folder_assignments()

            # Step 1: Fetch all folders
            logger.info("fetching_bookmark_folders")
            folders = await self.client.get_bookmark_folders()
            logger.info("folders_fetched", count=len(folders))

            # Save folder definitions
            for folder in folders:
                self.db.save_folder(folder.folder_id, folder.folder_name)

            # Step 2: Fetch ALL bookmarks with full data (single call, 800 max)
            logger.info("fetching_all_bookmarks_full_data")
            all_bookmarks_list, last_tweet_id = await self.client.get_all_bookmarks()
            all_bookmarks: dict[str, Bookmark] = {b.tweet_id: b for b in all_bookmarks_list}
            logger.info("all_bookmarks_fetched", count=len(all_bookmarks))

            # Step 3: Fetch bookmark IDs per folder and cross-reference
            bookmark_folders: dict[str, set[str]] = {}  # tweet_id -> set of folder_ids

            for folder in folders:
                logger.info("fetching_bookmark_ids_for_folder", folder_id=folder.folder_id, folder_name=folder.folder_name)
                folder_tweet_ids = await self.client.get_all_folder_bookmark_ids(folder_id=folder.folder_id)

                for tweet_id in folder_tweet_ids:
                    if tweet_id not in bookmark_folders:
                        bookmark_folders[tweet_id] = set()
                    bookmark_folders[tweet_id].add(folder.folder_id)

                logger.info("folder_bookmark_ids_fetched", folder=folder.folder_name, count=len(folder_tweet_ids))

            # Any bookmark not in bookmark_folders is uncategorized (no folder assignment needed)

            # Step 4: Save all bookmarks and folder assignments
            logger.info("saving_bookmarks", total=len(all_bookmarks))
            new_count = 0
            for tweet_id, bookmark in all_bookmarks.items():
                # Save bookmark
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
                new_count += 1

                # Save folder assignments
                folder_ids = bookmark_folders.get(tweet_id, set())
                for folder_id in folder_ids:
                    self.db.assign_bookmark_to_folder(tweet_id, folder_id)

            # Update sync status
            total_count = len(all_bookmarks)
            self.db.update_sync_status(
                last_tweet_id=last_tweet_id,
                total_bookmarks=total_count,
                sync_in_progress=False,
                first_sync_complete=True
            )

            logger.info(
                "sync_completed",
                new_bookmarks=new_count,
                total_bookmarks=total_count,
                folder_count=len(folders),
                full_sync=full_sync
            )

            return {
                "status": "success",
                "new_bookmarks": new_count,
                "total_bookmarks": total_count,
                "folder_count": len(folders),
                "full_sync": full_sync
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
