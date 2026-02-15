"""Configuration management for Jarvis Bot.

Uses pydantic-settings for environment variable validation.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_POLLING_INTERVAL = 0.5
MIN_POLLING_TIMEOUT = 10
MAX_POLLING_TIMEOUT = 120


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram settings
    telegram_bot_id: str = Field(
        description="Telegram bot token from @BotFather"
    )
    telegram_user_id: int = Field(
        description="Authorized Telegram user ID"
    )
    telegram_polling_interval: float = Field(
        default=1.0,
        description="Seconds between polling requests",
    )
    telegram_polling_timeout: int = Field(
        default=30,
        description="Timeout for getUpdates request in seconds",
    )

    # OpenCode Server settings
    opencode_url: str = Field(
        default="http://localhost:4096",
        description="OpenCode Server HTTP URL",
    )
    opencode_server_password: str = Field(
        description="OpenCode Server password for authentication"
    )

    # Database settings
    database_path: str = Field(
        default=".jarvis/jarvis.db",
        description="Path to SQLite database",
    )
    enable_message_audit: bool = Field(
        default=True,
        description="Enable message audit logging",
    )
    favorite_models_path: str = Field(
        default=".jarvis/favorite_models.json",
        description="Path to favorite models JSON file",
    )

    # Application settings
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    jarvis_env: str = Field(
        default="production",
        description="Environment name (development, production)",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the allowed values."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got {v}")
        return v_upper

    @field_validator("telegram_user_id")
    @classmethod
    def validate_user_id(cls, v: int) -> int:
        """Validate user ID is positive."""
        if v <= 0:
            raise ValueError(f"telegram_user_id must be positive, got {v}")
        return v

    @field_validator("telegram_polling_interval")
    @classmethod
    def validate_polling_interval(cls, v: float) -> float:
        """Validate polling interval is reasonable."""
        if v < MIN_POLLING_INTERVAL:
            raise ValueError(
                f"polling_interval must be >= {MIN_POLLING_INTERVAL}s, got {v}"
            )
        return v

    @field_validator("telegram_polling_timeout")
    @classmethod
    def validate_polling_timeout(cls, v: int) -> int:
        """Validate polling timeout is reasonable."""
        if v < MIN_POLLING_TIMEOUT or v > MAX_POLLING_TIMEOUT:
            raise ValueError(
                f"polling_timeout must be {MIN_POLLING_TIMEOUT}-{MAX_POLLING_TIMEOUT}s, got {v}"
            )
        return v

    @field_validator("database_path")
    @classmethod
    def expand_database_path(cls, v: str) -> str:
        """Expand user home in database path."""
        return str(Path(v).expanduser())

    @field_validator("favorite_models_path")
    @classmethod
    def expand_favorite_models_path(cls, v: str) -> str:
        """Expand user home in favorite models path."""
        return str(Path(v).expanduser())


def get_settings() -> Settings:
    """Get application settings singleton.

    Returns:
        Settings: Validated application settings.
    """
    return Settings()
