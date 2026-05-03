"""Configuration management via pydantic-settings."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.models import DEFAULT_MODEL_ID

MIN_POLLING_INTERVAL = 0.5
MIN_POLLING_TIMEOUT = 10
MAX_POLLING_TIMEOUT = 120
MIN_MEMORY_MAX_CHARS = 500


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    soul_path: str = Field(
        default="soul/SOUL.md",
        description="Path to the SOUL.md identity definition file",
    )

    model: str = Field(
        default=DEFAULT_MODEL_ID,
        description="PydanticAI model identifier (provider:model-name)",
    )

    telegram_bot_token: str = Field(
        description="Telegram bot token from @BotFather",
    )
    telegram_user_id: int = Field(
        description="Authorized Telegram user ID",
    )
    telegram_polling_interval: float = Field(
        default=1.0,
        description="Seconds between polling requests",
    )
    telegram_polling_timeout: int = Field(
        default=30,
        description="Timeout for getUpdates request in seconds",
    )

    database_path: str = Field(
        default="vault/index/alfred.db",
        description="Path to SQLite database",
    )

    memory_max_chars: int = Field(
        default=5000,
        description="Max characters for MEMORY.md",
    )
    user_profile_max_chars: int = Field(
        default=2000,
        description="Max characters for USER.md",
    )

    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    opencode_go_api_key: str = Field(
        default="",
        description="OpenCode Go API key (from opencode.ai/auth)",
    )
    opencode_go_base_url: str = Field(
        default="https://opencode.ai/zen/go/v1",
        description="OpenCode Go API base URL",
    )
    alfred_env: str = Field(
        default="production",
        description="Environment name (development, production)",
    )

    polling_max_backoff_level: int = Field(
        default=6,
        description="Max exponential backoff level (~64s max delay)",
    )
    polling_max_backoff_seconds: int = Field(
        default=60,
        description="Cap for backoff delay in seconds",
    )

    vault_root: str = Field(
        default="vault",
        description="Root directory for vault artifacts",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got {v}")
        return v_upper

    @field_validator("telegram_user_id")
    @classmethod
    def validate_user_id(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"telegram_user_id must be positive, got {v}")
        return v

    @field_validator("telegram_polling_interval")
    @classmethod
    def validate_polling_interval(cls, v: float) -> float:
        if v < MIN_POLLING_INTERVAL:
            raise ValueError(
                f"polling_interval must be >= {MIN_POLLING_INTERVAL}s, got {v}"
            )
        return v

    @field_validator("telegram_polling_timeout")
    @classmethod
    def validate_polling_timeout(cls, v: int) -> int:
        if v < MIN_POLLING_TIMEOUT or v > MAX_POLLING_TIMEOUT:
            raise ValueError(
                f"polling_timeout must be {MIN_POLLING_TIMEOUT}-{MAX_POLLING_TIMEOUT}s, got {v}"
            )
        return v

    @field_validator("database_path", "vault_root", "soul_path")
    @classmethod
    def expand_user_paths(cls, v: str) -> str:
        return str(Path(v).expanduser())

    @field_validator("memory_max_chars", "user_profile_max_chars")
    @classmethod
    def validate_memory_limits(cls, v: int) -> int:
        if v < MIN_MEMORY_MAX_CHARS:
            raise ValueError(
                f"memory/user_profile max chars must be >= {MIN_MEMORY_MAX_CHARS}, got {v}"
            )
        return v


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
