"""Configuration management for Jarvis Bot.

Uses pydantic-settings for environment variable validation.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Telegram settings
    telegram_bot_id: str = Field(
        description="Telegram bot token from @BotFather"
    )
    telegram_user_id: int = Field(
        description="Authorized Telegram user ID"
    )
    telegram_polling_interval: float = Field(
        default=2.0,
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

    # Application settings
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    jarvis_env: str = Field(
        default="production",
        description="Environment name (development, production)",
    )
    session_storage_path: str = Field(
        default=".jarvis/sessions.json",
        description="Path to store user session mappings",
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
        if v < 0.5:
            raise ValueError(f"polling_interval must be >= 0.5s, got {v}")
        return v

    @field_validator("telegram_polling_timeout")
    @classmethod
    def validate_polling_timeout(cls, v: int) -> int:
        """Validate polling timeout is reasonable."""
        if v < 10 or v > 120:
            raise ValueError(f"polling_timeout must be 10-120s, got {v}")
        return v

    @field_validator("session_storage_path")
    @classmethod
    def expand_session_storage_path(cls, v: str) -> str:
        """Expand user home in session storage path."""
        return str(Path(v).expanduser())

    @field_validator("database_path")
    @classmethod
    def expand_database_path(cls, v: str) -> str:
        """Expand user home in database path."""
        return str(Path(v).expanduser())


def get_settings() -> Settings:
    """Get application settings singleton.

    Returns:
        Settings: Validated application settings.
    """
    return Settings()
