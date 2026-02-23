"""OpenCode session management.

Handles session creation, lookup, and lifecycle for user conversations.
Sessions are stored in SQLite for data sovereignty and audit trail.
A new session is created on every bot restart to ensure clean state.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from jarvis.exceptions import DatabaseError
from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.database import Database
    from jarvis.opencode_client import OpenCodeClient

logger = get_logger(__name__)


class SessionManager:
    """Manages OpenCode sessions with per-restart creation.

    Sessions are stored in SQLite for data sovereignty:
    - New session created on every bot restart
    - Full audit history of all sessions
    - Uses timestamp (not just date) for unique session titles
    """

    def __init__(self, opencode: "OpenCodeClient", db: "Database") -> None:
        """Initialize session manager.

        Args:
            opencode: OpenCode client instance.
            db: Database instance for session storage.
        """
        self._opencode = opencode
        self._db = db
        # In-memory cache for current session
        self._sessions: dict[int, str] = {}
        # Track if we've created a session this bot instance
        self._session_created_for_user: set[int] = set()

    def get_session(self, user_id: int) -> str | None:
        """Get cached session ID for user.

        Args:
            user_id: Telegram user ID.

        Returns:
            Session ID or None if not cached.
        """
        return self._sessions.get(user_id)

    def set_session(self, user_id: int, session_id: str) -> None:
        """Set session ID for user (manual override).

        Used by command handlers for /new and /switch commands.

        Args:
            user_id: Telegram user ID.
            session_id: OpenCode session ID.
        """
        self._sessions[user_id] = session_id

    async def get_or_create_session(self, user_id: int) -> tuple[str, bool]:
        """Get or create session for user.

        Creates a new session on every bot restart (tracked via _session_created_for_user).
        Session title includes full timestamp for uniqueness.

        Args:
            user_id: Telegram user ID.

        Returns:
            Tuple of (session_id, is_new_session).
            - session_id: The OpenCode session ID.
            - is_new_session: True if a new session was created, False if existing.

        Raises:
            RuntimeError: If session cannot be created.
        """
        # Check if we already have a session for this user in this bot instance
        if user_id in self._sessions:
            return self._sessions[user_id], False

        # Check if we've already created a session this bot instance
        if user_id in self._session_created_for_user:
            # Should not happen, but safety check
            return self._sessions[user_id], False

        # Create new session with unique timestamp
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d-%H%M%S")
        session_title = f"jarvis-user-{user_id}-{timestamp}"

        try:
            session_id = await self._opencode.create_session(session_title)
        except Exception as e:
            logger.error(
                "session_creation_failed",
                user_id=user_id,
                error=str(e),
            )
            raise RuntimeError(f"Failed to create session for user {user_id}: {e}") from e

        # Cache in memory
        self._sessions[user_id] = session_id
        self._session_created_for_user.add(user_id)

        # Store in database for audit trail (use date for date_key)
        today = now.date().isoformat()
        try:
            self._db.create_session_record(user_id, session_id, session_title)
        except DatabaseError as e:
            # Log but don't fail - we still have the session
            logger.warning(
                "session_record_create_failed",
                user_id=user_id,
                session_id=session_id,
                error=str(e),
            )

        logger.info(
            "session_created",
            user_id=user_id,
            session_id=session_id,
            title=session_title,
        )
        return session_id, True

    def update_session_model(self, session_id: str, model: str) -> None:
        """Update the model used for a session.

        Args:
            session_id: OpenCode session ID.
            model: Model ID used (e.g., "zai/glm-4.7").
        """
        self._db.update_session_model(session_id, model)

    def get_session_history(self, user_id: int, limit: int = 10) -> list[dict[str, str]]:
        """Get recent session history for a user.

        Args:
            user_id: Telegram user ID.
            limit: Maximum number of sessions to return.

        Returns:
            List of session records.
        """
        return self._db.get_session_history(user_id, limit)
