"""Scheduled sync for X bookmarks.

Handles full sync on first run, incremental sync thereafter.
"""

import json
from typing import Any

from jarvis.bookmarks.client import XAPIClient
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
            last_id = sync_status.get("last_tweet_id") if sync_status else None
            first_ever_sync = not sync_status or not last_id

            if full_sync or first_ever_sync:
                logger.info("full_sync_triggered", first_ever=first_ever_sync)
                since_id = None
            else:
                since_id = last_id
                logger.info("incremental_sync_triggered", since_id=since_id)

            bookmarks, last_tweet_id = await self.client.get_all_bookmarks(since_id=since_id)

            new_count = 0
            for bookmark in bookmarks:
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

            total_count = (sync_status.get("total_bookmarks", 0) if sync_status else 0) + new_count

            self.db.update_sync_status(
                last_tweet_id=last_tweet_id,
                total_bookmarks=total_count,
                sync_in_progress=False,
                first_sync_complete=True if (full_sync or first_ever_sync) else None
            )

            logger.info(
                "sync_completed",
                new_bookmarks=new_count,
                total_bookmarks=total_count,
                full_sync=full_sync or first_ever_sync
            )

            return {
                "status": "success",
                "new_bookmarks": new_count,
                "total_bookmarks": total_count,
                "full_sync": full_sync or first_ever_sync
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
