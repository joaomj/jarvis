"""OAuth token storage operations."""

import sqlite3

from jarvis.database.core import DatabaseCore
from jarvis.exceptions import DatabaseError
from jarvis.logging_config import get_logger

logger = get_logger(__name__)


class OAuthOperations(DatabaseCore):
    """X OAuth token storage and management."""

    def save_oauth_tokens(
        self,
        access_token: str,
        refresh_token: str,
        expires_at: str,
        scope: str | None = None,
    ) -> None:
        """Save or update OAuth tokens.

        Args:
            access_token: OAuth 2.0 access token.
            refresh_token: OAuth 2.0 refresh token.
            expires_at: Token expiration timestamp (ISO format).
            scope: Granted scopes.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO x_oauth_tokens (id, access_token, refresh_token, expires_at, scope)
                       VALUES (1, ?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET
                           access_token = excluded.access_token,
                           refresh_token = excluded.refresh_token,
                           expires_at = excluded.expires_at,
                           scope = excluded.scope,
                           updated_at = CURRENT_TIMESTAMP""",
                    (access_token, refresh_token, expires_at, scope),
                )
                logger.info("oauth_tokens_saved")
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.error("save_oauth_tokens_failed", error=str(e))
            raise DatabaseError(
                "Failed to save OAuth tokens",
                operation="save_oauth_tokens",
                details=str(e),
            ) from e

    def get_oauth_tokens(self) -> dict | None:
        """Get stored OAuth tokens.

        Returns:
            Dictionary with access_token, refresh_token, expires_at, scope or None.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """SELECT access_token, refresh_token, expires_at, scope
                       FROM x_oauth_tokens WHERE id = 1""",
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                return {
                    "access_token": row[0],
                    "refresh_token": row[1],
                    "expires_at": row[2],
                    "scope": row[3],
                }
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("get_oauth_tokens_failed", error=str(e))
            return None

    def update_access_token(
        self,
        access_token: str,
        expires_at: str,
    ) -> None:
        """Update access token after refresh.

        Args:
            access_token: New access token.
            expires_at: New expiration timestamp.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """UPDATE x_oauth_tokens
                       SET access_token = ?, expires_at = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = 1""",
                    (access_token, expires_at),
                )
                logger.info("access_token_refreshed")
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError) as e:
            logger.warning("update_access_token_failed", error=str(e))

    def has_oauth_tokens(self) -> bool:
        """Check if OAuth tokens are stored.

        Returns:
            bool: True if tokens exist.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT 1 FROM x_oauth_tokens WHERE id = 1")
                return cursor.fetchone() is not None
        except (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError):
            return False
