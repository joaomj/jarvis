"""X API client for bookmarks using OAuth 2.0 user-context."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from jarvis.bookmarks.client_fetch import XAPIClientFetchMixin
from jarvis.database import Database
from jarvis.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_X_API_BASE_URL = "https://api.x.com/2"
DEFAULT_X_OAUTH_TOKEN_URL = "https://api.x.com/2/oauth2/token"  # noqa: S105


class XAPIClient(XAPIClientFetchMixin):
    """X API client with OAuth token refresh support."""

    def __init__(  # noqa: PLR0913
        self,
        db: Database,
        client_id: str,
        client_secret: str,
        base_url: str = DEFAULT_X_API_BASE_URL,
        oauth_token_url: str = DEFAULT_X_OAUTH_TOKEN_URL,
        api_timeout: float = 30.0,
        token_refresh_buffer_seconds: int = 300,
    ) -> None:
        self.db = db
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.oauth_token_url = oauth_token_url
        self.api_timeout = api_timeout
        self._token_refresh_buffer = token_refresh_buffer_seconds
        self.client = httpx.AsyncClient(timeout=api_timeout)
        self._user_id: str | None = None
        logger.info("x_client_initialized")

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()
        logger.info("x_client_closed")

    def _is_token_expired(self, expires_at: str) -> bool:
        """Return True when token is expired (or near expiry)."""
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            now = datetime.now(UTC)
            return (expiry - now).total_seconds() < self._token_refresh_buffer
        except (ValueError, TypeError):
            return True

    async def _refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Refresh access token using refresh token."""
        response = await self.client.post(
            self.oauth_token_url,
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            auth=(self.client_id, self.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        return response.json()

    async def _get_valid_access_token(self) -> str:
        """Return a valid access token, refreshing if needed."""
        tokens = self.db.get_oauth_tokens()
        if not tokens:
            raise RuntimeError(
                "No OAuth tokens stored. Run 'python scripts/setup_x_oauth.py' first."
            )

        access_token = tokens["access_token"]
        expires_at = tokens["expires_at"]
        refresh_token = tokens["refresh_token"]
        if not self._is_token_expired(expires_at):
            return access_token

        logger.info("token_expired_refreshing")
        try:
            token_data = await self._refresh_access_token(refresh_token)
            access_token = token_data["access_token"]
            new_refresh_token = token_data.get("refresh_token", refresh_token)
            expires_in = token_data["expires_in"]
            expires_at_iso = datetime.fromtimestamp(
                datetime.now(UTC).timestamp() + expires_in, tz=UTC
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
            return access_token
        except Exception as error:
            logger.error("token_refresh_failed", error=str(error))
            raise RuntimeError(f"Failed to refresh token: {error}") from error

    async def _get_user_id(self) -> str:
        """Get authenticated user's X user ID."""
        if self._user_id is not None:
            return self._user_id

        access_token = await self._get_valid_access_token()
        try:
            response = await self.client.get(
                f"{self.base_url}/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            user_id = response.json()["data"]["id"]
            self._user_id = user_id
            logger.info("user_id_fetched", user_id=user_id)
            return user_id
        except Exception as error:
            logger.error("user_id_fetch_failed", error=str(error))
            raise RuntimeError(f"Failed to get user ID: {error}") from error
