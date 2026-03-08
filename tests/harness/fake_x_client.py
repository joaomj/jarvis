"""Fake X API client for deterministic testing without network calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jarvis.bookmarks.models import Bookmark, BookmarkFolder


@dataclass
class FakeBookmarkData:
    """Fake bookmark data for testing."""

    tweet_id: str
    text: str
    author_id: str
    username: str
    name: str
    created_at: str = "2024-01-01T00:00:00.000Z"
    like_count: int = 100
    retweet_count: int = 50
    reply_count: int = 10
    impression_count: int = 1000
    bookmark_count: int = 5
    verified: bool = False
    urls: list[str] = field(default_factory=list)
    note_text: str | None = None

    def to_api_format(self) -> dict[str, Any]:
        """Convert to X API response format."""
        return {
            "id": self.tweet_id,
            "text": self.text,
            "author_id": self.author_id,
            "created_at": self.created_at,
            "public_metrics": {
                "like_count": self.like_count,
                "retweet_count": self.retweet_count,
                "reply_count": self.reply_count,
                "impression_count": self.impression_count,
                "bookmark_count": self.bookmark_count,
            },
            "entities": {"urls": [{"expanded_url": url} for url in self.urls]} if self.urls else {},
            "note_text": self.note_text,
        }

    def to_author_format(self) -> dict[str, Any]:
        """Convert to X API author format."""
        return {
            "id": self.author_id,
            "username": self.username,
            "name": self.name,
            "verified": self.verified,
        }


class FakeXAPIClient:
    """Deterministic fake X API client for testing.

    Simulates X API behavior without network calls:
    - OAuth token management
    - Bookmark pagination
    - Folder operations
    - Error scenarios

    Usage:
        fake_client = FakeXAPIClient()
        fake_client.add_bookmark(FakeBookmarkData(...))
        bookmarks, last_id = await fake_client.get_all_bookmarks()
    """

    def __init__(
        self,
        user_id: str = "test_user_123",
        access_token: str = "fake_access_token",  # noqa: S107
        should_refresh_token: bool = False,
    ):
        self._user_id = user_id
        self._access_token = access_token
        self._refresh_token = "fake_refresh_token"
        self._expires_at = "2099-12-31T23:59:59+00:00"
        self._should_refresh_token = should_refresh_token
        self._closed = False

        self._bookmarks: dict[str, FakeBookmarkData] = {}
        self._folders: dict[str, str] = {}  # folder_id -> folder_name
        self._folder_bookmarks: dict[str, list[str]] = {}  # folder_id -> [tweet_id, ...]

        self._call_log: list[dict[str, Any]] = []

    def add_bookmark(self, bookmark: FakeBookmarkData) -> None:
        """Add a bookmark to the fake dataset."""
        self._bookmarks[bookmark.tweet_id] = bookmark

    def add_folder(self, folder_id: str, folder_name: str) -> None:
        """Add a folder to the fake dataset."""
        self._folders[folder_id] = folder_name
        if folder_id not in self._folder_bookmarks:
            self._folder_bookmarks[folder_id] = []

    def add_bookmark_to_folder(self, folder_id: str, tweet_id: str) -> None:
        """Add a bookmark to a folder."""
        if folder_id not in self._folder_bookmarks:
            self._folder_bookmarks[folder_id] = []
        if tweet_id not in self._folder_bookmarks[folder_id]:
            self._folder_bookmarks[folder_id].append(tweet_id)

    def set_token_expired(self, expired: bool = True) -> None:
        """Set whether token should be considered expired."""
        self._should_refresh_token = expired

    async def close(self) -> None:
        """Close the fake client."""
        self._closed = True

    async def _get_valid_access_token(self) -> str:
        """Return access token, refresh if marked as expired."""
        if self._should_refresh_token:
            self._access_token = "refreshed_access_token"
            self._should_refresh_token = False
        return self._access_token

    async def _get_user_id(self) -> str:
        """Return the fake user ID."""
        return self._user_id

    async def get_bookmark_folders(self) -> list[BookmarkFolder]:
        """Return fake bookmark folders."""
        self._call_log.append({"method": "get_bookmark_folders"})
        return [
            BookmarkFolder(folder_id=folder_id, folder_name=name)
            for folder_id, name in self._folders.items()
        ]

    async def get_bookmarks(
        self,
        since_id: str | None = None,
        pagination_token: str | None = None,
        max_results: int = 100,
    ) -> dict[str, Any]:
        """Return bookmarks in X API format with optional pagination."""
        self._call_log.append(
            {
                "method": "get_bookmarks",
                "since_id": since_id,
                "pagination_token": pagination_token,
                "max_results": max_results,
            }
        )

        # Filter by since_id if provided
        filtered_bookmarks = list(self._bookmarks.values())
        if since_id:
            filtered_bookmarks = [b for b in filtered_bookmarks if int(b.tweet_id) > int(since_id)]

        # Simple pagination: use pagination_token as page number
        page_size = min(max_results, 100)
        page_num = int(pagination_token) if pagination_token else 0
        start_idx = page_num * page_size
        end_idx = start_idx + page_size
        page_bookmarks = filtered_bookmarks[start_idx:end_idx]

        # Check if there are more pages
        next_token = str(page_num + 1) if end_idx < len(filtered_bookmarks) else None

        return {
            "data": [b.to_api_format() for b in page_bookmarks],
            "includes": {
                "users": list({b.author_id: b.to_author_format() for b in page_bookmarks}.values())
            },
            "meta": {"result_count": len(page_bookmarks), "next_token": next_token},
        }

    async def get_folder_bookmark_ids(
        self,
        folder_id: str,
        pagination_token: str | None = None,
    ) -> dict[str, Any]:
        """Return bookmark IDs from a folder with pagination."""
        self._call_log.append(
            {
                "method": "get_folder_bookmark_ids",
                "folder_id": folder_id,
                "pagination_token": pagination_token,
            }
        )

        bookmark_ids = self._folder_bookmarks.get(folder_id, [])

        # Pagination
        page_size = 100
        page_num = int(pagination_token) if pagination_token else 0
        start_idx = page_num * page_size
        end_idx = start_idx + page_size
        page_ids = bookmark_ids[start_idx:end_idx]

        next_token = str(page_num + 1) if end_idx < len(bookmark_ids) else None

        return {
            "data": [{"id": tweet_id} for tweet_id in page_ids],
            "meta": {"result_count": len(page_ids), "next_token": next_token},
        }

    async def get_all_folder_bookmark_ids(self, folder_id: str) -> list[str]:
        """Get all bookmark IDs from a folder with pagination."""
        all_ids: list[str] = []
        pagination_token: str | None = None

        while True:
            data = await self.get_folder_bookmark_ids(
                folder_id=folder_id, pagination_token=pagination_token
            )
            tweet_list = data.get("data", [])
            if not tweet_list:
                break
            all_ids.extend(tweet["id"] for tweet in tweet_list if tweet.get("id"))

            pagination_token = data.get("meta", {}).get("next_token")
            if not pagination_token:
                break

        return all_ids

    async def get_all_bookmarks(
        self, since_id: str | None = None
    ) -> tuple[list[Bookmark], str | None]:
        """Get all bookmarks with full data and pagination."""
        from jarvis.bookmarks.parser import parse_bookmark

        all_bookmarks: list[Bookmark] = []
        last_tweet_id: str | None = None
        pagination_token: str | None = None

        while True:
            data = await self.get_bookmarks(since_id=since_id, pagination_token=pagination_token)
            tweet_list = data.get("data", [])
            if not tweet_list:
                break

            users_by_id = {
                user["id"]: user
                for user in data.get("includes", {}).get("users", [])
                if user.get("id")
            }
            for tweet_data in tweet_list:
                try:
                    bookmark = parse_bookmark(tweet_data, users_by_id)
                    all_bookmarks.append(bookmark)
                    if not last_tweet_id or int(bookmark.tweet_id) > int(last_tweet_id):
                        last_tweet_id = bookmark.tweet_id
                except Exception:  # noqa: S110  # Skip malformed bookmarks like real implementation
                    pass

            pagination_token = data.get("meta", {}).get("next_token")
            if not pagination_token:
                break

        return all_bookmarks, last_tweet_id

    @property
    def call_log(self) -> list[dict[str, Any]]:
        """Return log of all API calls made."""
        return self._call_log.copy()

    @property
    def is_closed(self) -> bool:
        """Return True if client has been closed."""
        return self._closed
