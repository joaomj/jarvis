"""X API client for bookmarks using OAuth 2.0 user-context.

Supports automatic token refresh when expired.
"""

from datetime import UTC, datetime
from typing import Any

import httpx

from jarvis.bookmarks.models import Bookmark
from jarvis.bookmarks.parser import parse_bookmark
from jarvis.database import Database
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class XAPIClient:
    """X API client for bookmarks using OAuth 2.0 user-context."""

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
        """Initialize X API client.

        Args:
            db: Database instance for token storage.
            client_id: OAuth 2.0 Client ID.
            client_secret: OAuth 2.0 Client Secret.
            base_url: X API base URL.
            oauth_token_url: OAuth 2.0 token endpoint URL.
            api_timeout: Request timeout in seconds.
            token_refresh_buffer_seconds: Seconds before expiry to refresh token.
        """
        self.db = db
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.oauth_token_url = oauth_token_url
        self.api_timeout = api_timeout
        self._token_refresh_buffer = token_refresh_buffer_seconds
        self.client = httpx.AsyncClient(timeout=api_timeout)
        self._access_token: str | None = None
        self._user_id: str | None = None
        logger.info("x_client_initialized")

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
        logger.info("x_client_closed")

    def _is_token_expired(self, expires_at: str) -> bool:
        """Check if token is expired or about to expire.

        Args:
            expires_at: Token expiration timestamp (ISO format).

        Returns:
            True if token is expired or will expire within buffer period.
        """
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            now = datetime.now(UTC)
            buffer = self._token_refresh_buffer
            return (expiry - now).total_seconds() < buffer
        except (ValueError, TypeError):
            return True

    async def _refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh access token using refresh token.

        Args:
            refresh_token: OAuth 2.0 refresh token.

        Returns:
            Token response with new access_token, refresh_token, expires_in.
        """
        response = await self.client.post(
            self.oauth_token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(self.client_id, self.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()

    async def _get_valid_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token.

        Raises:
            RuntimeError: If no tokens are stored or refresh fails.
        """
        tokens = self.db.get_oauth_tokens()
        if not tokens:
            raise RuntimeError(
                "No OAuth tokens stored. Run 'python scripts/setup_x_oauth.py' first."
            )

        access_token = tokens["access_token"]
        expires_at = tokens["expires_at"]
        refresh_token = tokens["refresh_token"]

        if self._is_token_expired(expires_at):
            logger.info("token_expired_refreshing")
            try:
                token_data = await self._refresh_access_token(refresh_token)
                access_token = token_data["access_token"]
                new_refresh_token = token_data.get("refresh_token", refresh_token)
                expires_in = token_data["expires_in"]
                new_expires_at = datetime.now(UTC).timestamp() + expires_in
                expires_at_iso = datetime.fromtimestamp(
                    new_expires_at, tz=UTC
                ).isoformat()

                self.db.update_access_token(access_token, expires_at_iso)

                if new_refresh_token != refresh_token:
                    self.db.save_oauth_tokens(
                        access_token=access_token,
                        refresh_token=new_refresh_token,
                        expires_at=expires_at_iso,
                        scope=tokens.get("scope"),
                    )

                logger.info("token_refreshed_successfully")
            except Exception as e:
                logger.error("token_refresh_failed", error=str(e))
                raise RuntimeError(f"Failed to refresh token: {e}") from e

        return access_token

    async def _get_user_id(self) -> str:
        """Get authenticated user's X user ID.

        Returns:
            User ID string.

        Raises:
            RuntimeError: If unable to fetch user ID.
        """
        if self._user_id is not None:
            return self._user_id

        access_token = await self._get_valid_access_token()

        try:
            response = await self.client.get(
                f"{self.base_url}/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            user_id = data["data"]["id"]
            self._user_id = user_id
            logger.info("user_id_fetched", user_id=user_id)
            return user_id
        except Exception as e:
            logger.error("user_id_fetch_failed", error=str(e))
            raise RuntimeError(f"Failed to get user ID: {e}") from e

    async def get_bookmarks(
        self,
        since_id: str | None = None,
        pagination_token: str | None = None,
        max_results: int = 100,
    ) -> dict[str, Any]:
        """Get user bookmarks from X API.

        Args:
            since_id: Only return bookmarks with ID greater than this.
            pagination_token: Token for next page.
            max_results: Number of bookmarks to fetch per request (max 100).

        Returns:
            API response JSON.
        """
        access_token = await self._get_valid_access_token()
        user_id = await self._get_user_id()

        params: dict[str, str | int] = {
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,public_metrics,author_id,entities,context_annotations",
            "user.fields": "username,name,verified",
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
        except httpx.HTTPStatusError as e:
            logger.error("bookmarks_fetch_failed", status_code=e.response.status_code, error=str(e))
            raise
        except httpx.RequestError as e:
            logger.error("bookmarks_fetch_error", error=str(e))
            raise

    async def get_all_bookmarks(
        self,
        since_id: str | None = None,
    ) -> tuple[list[Bookmark], str | None]:
        """Get all bookmarks with pagination.

        Args:
            since_id: Only return bookmarks with ID greater than this.

        Returns:
            Tuple of (bookmarks list, last tweet ID).
        """
        all_bookmarks: list[Bookmark] = []
        last_tweet_id = None
        pagination_token = None

        while True:
            try:
                data = await self.get_bookmarks(
                    since_id=since_id,
                    pagination_token=pagination_token
                )

                tweet_list = data.get("data", [])
                if not tweet_list:
                    break

                users_by_id = {}
                if "includes" in data and "users" in data["includes"]:
                    users_by_id = {u["id"]: u for u in data["includes"]["users"]}

                for tweet_data in tweet_list:
                    try:
                        bookmark = parse_bookmark(tweet_data, users_by_id)
                        all_bookmarks.append(bookmark)
                        if not last_tweet_id or int(bookmark.tweet_id) > int(last_tweet_id):
                            last_tweet_id = bookmark.tweet_id
                    except Exception as e:
                        logger.warning(
                            "bookmark_parse_failed",
                            tweet_id=tweet_data.get("id"),
                            error=str(e),
                        )

                meta = data.get("meta", {})
                pagination_token = meta.get("next_token")
                if not pagination_token:
                    break

            except Exception as e:
                logger.error("bookmarks_pagination_failed", error=str(e), exc_info=True)
                break

        logger.info("all_bookmarks_fetched", total=len(all_bookmarks))
        return all_bookmarks, last_tweet_id
