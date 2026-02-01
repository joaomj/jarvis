"""Configuration management for Jarvis Bot.

Uses pydantic-settings for environment variable validation.
"""

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
    telegram_webhook_url: str = Field(
        description="Webhook URL (e.g., https://host.tailnet-name.ts.net/webhook)"
    )
    telegram_webhook_port: int = Field(
        default=8080,
        description="Local port for webhook server",
    )

    # OpenCode Server settings
    opencode_url: str = Field(
        default="http://opencode:4096",
        description="OpenCode Server HTTP URL",
    )
    opencode_server_password: str = Field(
        description="OpenCode Server password for authentication"
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
        default="/app/data/sessions.json",
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

    @field_validator("telegram_webhook_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port is in valid range."""
        if not (1 <= v <= 65535):
            raise ValueError(f"Port must be between 1-65535, got {v}")
        return v


def get_settings() -> Settings:
    """Get application settings singleton.
    
    Returns:
        Settings: Validated application settings.
    """
    return Settings()
