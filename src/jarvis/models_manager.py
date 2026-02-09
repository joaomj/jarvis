"""Favorite models manager with auto-reload.

Handles loading and formatting user's favorite models from JSON file.
Auto-reloads when file changes (based on mtime).
"""

import json
from pathlib import Path
from typing import Final

from jarvis.logging_config import get_logger

logger = get_logger(__name__)

MAX_MODELS: Final = 10


class ModelsManager:
    """Manages user's favorite models from JSON file."""

    def __init__(self, file_path: str):
        """Initialize with path to favorite models JSON.

        Args:
            file_path: Path to JSON file containing array of model IDs.
        """
        self.file_path = Path(file_path)
        self._models: list[str] = []
        self._last_mtime: float = 0
        self._load()

    def _load(self) -> None:
        """Load models from JSON file."""
        if not self.file_path.exists():
            logger.warning(
                "favorite_models_file_missing",
                path=str(self.file_path),
            )
            self._models = []
            return

        try:
            content = self.file_path.read_text()
            data = json.loads(content)

            if not isinstance(data, list):
                logger.error(
                    "favorite_models_invalid_format",
                    error="JSON must be an array",
                )
                self._models = []
                return

            # Validate each item is string
            valid_models = [
                str(model).strip()
                for model in data
                if isinstance(model, str) and model.strip()
            ]

            # Enforce limit
            if len(valid_models) > MAX_MODELS:
                logger.warning(
                    "favorite_models_truncated",
                    original_count=len(valid_models),
                    max_allowed=MAX_MODELS,
                )
                valid_models = valid_models[:MAX_MODELS]

            self._models = valid_models
            self._last_mtime = self.file_path.stat().st_mtime

            logger.info(
                "favorite_models_loaded",
                count=len(self._models),
                path=str(self.file_path),
            )

        except json.JSONDecodeError as e:
            logger.error(
                "favorite_models_json_error",
                error=str(e),
            )
            self._models = []
        except Exception as e:
            logger.error(
                "favorite_models_load_failed",
                error=str(e),
            )
            self._models = []

    def _check_reload(self) -> None:
        """Reload file if modified."""
        try:
            if not self.file_path.exists():
                if self._models:  # Only clear if we had models before
                    logger.warning("favorite_models_file_removed")
                    self._models = []
                    self._last_mtime = 0
                return

            current_mtime = self.file_path.stat().st_mtime
            if current_mtime > self._last_mtime:
                logger.info("favorite_models_changed", reloading=True)
                self._load()

        except Exception as e:
            logger.error("favorite_models_reload_check_failed", error=str(e))

    def get_models(self) -> list[str]:
        """Get list of favorite models (auto-reloads if changed).

        Returns:
            List of model IDs, max 10 items.
        """
        self._check_reload()
        return self._models.copy()

    def format_telegram_list(self) -> str:
        """Format models as numbered HTML list for Telegram.

        Returns:
            Formatted string with HTML tags.
        """
        models = self.get_models()

        if not models:
            return "⚠️ No favorite models configured.\nCreate .jarvis/favorite_models.json"

        lines = []
        for i, model in enumerate(models, 1):
            # Escape HTML special chars in model ID
            escaped_model = model.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            lines.append(f"{i}. <code>{escaped_model}</code>")

        return "\n".join(lines)

    def get_model_by_number(self, number: int) -> str | None:
        """Get model ID by 1-indexed number.

        Args:
            number: 1-indexed selection number.

        Returns:
            Model ID if valid, None otherwise.
        """
        models = self.get_models()

        if number < 1 or number > len(models):
            return None

        return models[number - 1]  # Convert to 0-indexed

    def is_cancel(self, text: str) -> bool:
        """Check if text is a cancel command.

        Args:
            text: User's message text.

        Returns:
            True if text is "cancel" (case-insensitive).
        """
        return text.strip().lower() == "cancel"

    def get_count(self) -> int:
        """Get number of configured models."""
        return len(self.get_models())
