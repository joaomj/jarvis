"""Model selection flow for users.

Handles the interactive model selection process where users can pick
from their favorite models list.
"""

import html
from typing import TYPE_CHECKING

from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.database import Database
    from jarvis.models_manager import ModelsManager

logger = get_logger(__name__)


class ModelSelector:
    """Manages user model selection flow."""

    def __init__(self, db: "Database", models: "ModelsManager"):
        """Initialize model selector.

        Args:
            db: Database for storing user state.
            models: Models manager for available models.
        """
        self._db = db
        self._models = models
        self._preferences: dict[int, str] = {}

    def get_model_for_user(self, user_id: int) -> str | None:
        """Get model preference for user.

        Args:
            user_id: Telegram user ID.

        Returns:
            Model ID or None (use OpenCode default).
        """
        return self._preferences.get(user_id)

    def set_model_for_user(self, user_id: int, model_id: str) -> None:
        """Set model preference for user.

        Args:
            user_id: Telegram user ID.
            model_id: Model ID to set.
        """
        self._preferences[user_id] = model_id
        logger.info("model_preference_set", model=model_id, user_id=user_id)

    async def start_selection(self, user_id: int) -> str | None:
        """Start model selection flow.

        Args:
            user_id: Telegram user ID.

        Returns:
            Message to send to user, or None if no models configured.
        """
        model_count = self._models.get_count()
        if model_count == 0:
            return "No favorite models configured in vault/index/favorite_models.json"

        try:
            self._db.set_user_state(user_id, "awaiting_model_selection")
        except Exception as e:
            logger.error("set_user_state_failed", user_id=user_id, error=str(e))
            return "❌ Failed to start model selection. Please try again."

        model_list = self._models.format_telegram_list()
        return (
            "📋 <b>Available Models</b>\n\n"
            f"{model_list}\n\n"
            f"Reply with number (1-{model_count}) or <code>cancel</code>"
        )

    async def handle_selection(self, user_id: int, text: str) -> str:
        """Handle model selection response.

        Args:
            user_id: Telegram user ID.
            text: User's response text.

        Returns:
            Message to send to user.
        """
        if self._models.is_cancel(text):
            try:
                self._db.clear_user_state(user_id)
            except Exception as e:
                logger.warning("clear_user_state_failed", user_id=user_id, error=str(e))
            return "Model selection cancelled."

        if not text.strip().isdigit():
            return "Please reply with a model number or cancel."

        selected = int(text.strip())
        model_id = self._models.get_model_by_number(selected)

        if model_id is None:
            return f"Invalid selection. Choose 1-{self._models.get_count()} or cancel."

        try:
            self._db.clear_user_state(user_id)
        except Exception as e:
            logger.warning("clear_user_state_failed", user_id=user_id, error=str(e))

        self._preferences[user_id] = model_id
        logger.info("model_preference_set", model=model_id, user_id=user_id)

        return (
            f"✅ Model set to: <code>{html.escape(model_id)}</code>\n\n"
            "This will be used for your next message."
        )

    def is_awaiting_selection(self, user_id: int) -> bool:
        """Check if user is in model selection state.

        Args:
            user_id: Telegram user ID.

        Returns:
            True if user is awaiting model selection.
        """
        return self._db.get_user_state(user_id) == "awaiting_model_selection"
