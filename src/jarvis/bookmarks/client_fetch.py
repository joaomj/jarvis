"""Bookmark fetch and pagination methods for X API client."""

from __future__ import annotations

from typing import Any

import httpx

from jarvis.bookmarks.models import Bookmark, BookmarkFolder
from jarvis.bookmarks.parser import parse_bookmark
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class XAPIClientFetchMixin:
    """Fetch-related methods mixed into ``XAPIClient``."""

    client: httpx.AsyncClient
    base_url: str

    async def _get_valid_access_token(self) -> str:  # pragma: no cover
        raise NotImplementedError

    async def _get_user_id(self) -> str:  # pragma: no cover
        raise NotImplementedError

    async def get_bookmark_folders(self) -> list[BookmarkFolder]:
        """Get all bookmark folders for the authenticated user."""
        access_token = await self._get_valid_access_token()
        user_id = await self._get_user_id()

        try:
            response = await self.client.get(
                f"{self.base_url}/users/{user_id}/bookmarks/folders",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            folders_data = response.json().get("data", [])
            folders = [
                BookmarkFolder(folder_id=folder["id"], folder_name=folder["name"])
                for folder in folders_data
            ]
            logger.info("bookmark_folders_fetched", count=len(folders))
            return folders
        except httpx.HTTPStatusError as error:
            logger.error(
                "bookmark_folders_fetch_failed",
                status_code=error.response.status_code,
                error=str(error),
            )
            raise
        except httpx.RequestError as error:
            logger.error("bookmark_folders_fetch_error", error=str(error))
            raise

    async def get_bookmarks(
        self,
        since_id: str | None = None,
        pagination_token: str | None = None,
        max_results: int = 100,
    ) -> dict[str, Any]:
        """Get user bookmarks from X API with full data."""
        access_token = await self._get_valid_access_token()
        user_id = await self._get_user_id()

        params: dict[str, str | int] = {
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,author_id",
            "user.fields": "username",
            "expansions": "author_id",
        }
        if since_id:
            params["since_id"] = since_id
        if pagination_token:
            params["pagination_token"] = pagination_token

        try:
            response = await self.client.get(
                f"{self.base_url}/users/{user_id}/bookmarks",
                params=params,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            logger.info("bookmarks_page_fetched", count=data.get("meta", {}).get("result_count", 0))
            return data
        except httpx.HTTPStatusError as error:
            logger.error(
                "bookmarks_fetch_failed",
                status_code=error.response.status_code,
                error=str(error),
            )
            raise
        except httpx.RequestError as error:
            logger.error("bookmarks_fetch_error", error=str(error))
            raise

    async def get_folder_bookmark_ids(
        self,
        folder_id: str,
        pagination_token: str | None = None,
    ) -> dict[str, Any]:
        """Get bookmark IDs from a specific folder."""
        access_token = await self._get_valid_access_token()
        user_id = await self._get_user_id()
        params = {"pagination_token": pagination_token} if pagination_token else None

        try:
            response = await self.client.get(
                f"{self.base_url}/users/{user_id}/bookmarks/folders/{folder_id}",
                params=params,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
            logger.info(
                "folder_bookmark_ids_fetched",
                folder_id=folder_id,
                count=data.get("meta", {}).get("result_count", 0),
            )
            return data
        except httpx.HTTPStatusError as error:
            logger.error(
                "folder_bookmark_ids_fetch_failed",
                folder_id=folder_id,
                status_code=error.response.status_code,
                error=str(error),
            )
            raise
        except httpx.RequestError as error:
            logger.error("folder_bookmark_ids_fetch_error", folder_id=folder_id, error=str(error))
            raise

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

        logger.info("all_folder_bookmark_ids_fetched", folder_id=folder_id, total=len(all_ids))
        return all_ids

    async def get_all_bookmarks(
        self, since_id: str | None = None
    ) -> tuple[list[Bookmark], str | None]:
        """Get all bookmarks with full data and pagination."""
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
                except Exception as error:
                    logger.warning(
                        "bookmark_parse_failed",
                        tweet_id=tweet_data.get("id"),
                        error=str(error),
                    )

            pagination_token = data.get("meta", {}).get("next_token")
            if not pagination_token:
                break

        logger.info("all_bookmarks_fetched", total=len(all_bookmarks))
        return all_bookmarks, last_tweet_id
