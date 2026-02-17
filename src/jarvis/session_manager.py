"""OpenCode session management.

Handles session creation, lookup, and lifecycle for user conversations.
"""

from typing import TYPE_CHECKING

from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.opencode_client import OpenCodeClient

logger = get_logger(__name__)


class SessionManager:
    """Manages OpenCode sessions for users."""

    def __init__(self, opencode: "OpenCodeClient"):
        """Initialize session manager.

        Args:
            opencode: OpenCode client instance.
        """
        self._opencode = opencode
        self._sessions: dict[int, str] = {}

    def get_session(self, user_id: int) -> str | None:
        """Get cached session ID for user.

        Args:
            user_id: Telegram user ID.

        Returns:
            Session ID or None if not cached.
        """
        return self._sessions.get(user_id)

    def set_session(self, user_id: int, session_id: str) -> None:
        """Cache session ID for user.

        Args:
            user_id: Telegram user ID.
            session_id: OpenCode session ID.
        """
        self._sessions[user_id] = session_id

    async def get_or_create_session(self, user_id: int) -> str:
        """Find existing session by title or create new one.

        Args:
            user_id: Telegram user ID.

        Returns:
            OpenCode session ID.

        Raises:
            RuntimeError: If session cannot be created.
        """
        if user_id in self._sessions:
            session_id = self._sessions[user_id]
            logger.info("session_found_in_memory", user_id=user_id, session_id=session_id)
            return session_id

        session_title = f"jarvis-user-{user_id}"
        sessions = await self._opencode.list_sessions()
        user_session = next(
            (s for s in sessions if s.get("title") == session_title),
            None
        )

        if user_session:
            session_id = user_session["id"]
            self._sessions[user_id] = session_id
            logger.info("session_found_in_opencode", user_id=user_id, session_id=session_id)
            return session_id

        session_id = await self._opencode.create_session(session_title)
        self._sessions[user_id] = session_id
        logger.info("session_created", user_id=user_id, session_id=session_id)
        return session_id

    def clear_session(self, user_id: int) -> None:
        """Clear cached session for user.

        Args:
            user_id: Telegram user ID.
        """
        self._sessions.pop(user_id, None)
