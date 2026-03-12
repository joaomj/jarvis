"""Configuration management for Jarvis Bot.

Uses pydantic-settings for environment variable validation.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_POLLING_INTERVAL = 0.5
MIN_POLLING_TIMEOUT = 10
MAX_POLLING_TIMEOUT = 120
QMD_MAX_TIMEOUT_SECONDS = 300
QMD_MAX_SEARCH_LIMIT = 100


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram settings
    telegram_bot_id: str = Field(description="Telegram bot token from @BotFather")
    telegram_user_id: int = Field(description="Authorized Telegram user ID")
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
    opencode_server_password: str = Field(description="OpenCode Server password for authentication")

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

    # X (Twitter) API settings
    x_bearer_token: str | None = Field(
        default=None,
        description="X API Bearer token (read-only, from developer.twitter.com) - DEPRECATED, use OAuth 2.0",
    )
    x_client_id: str | None = Field(
        default=None,
        description="X OAuth 2.0 Client ID from Developer Console",
    )
    x_client_secret: str | None = Field(
        default=None,
        description="X OAuth 2.0 Client Secret from Developer Console",
    )
    x_api_base_url: str = Field(
        default="https://api.twitter.com/2",
        description="X API base URL",
    )
    x_oauth_token_url: str = Field(
        default="https://api.x.com/2/oauth2/token",
        description="X OAuth 2.0 token endpoint URL",
    )
    x_api_timeout: float = Field(
        default=30.0,
        description="X API request timeout in seconds",
    )
    x_token_refresh_buffer_seconds: int = Field(
        default=300,
        description="Seconds before expiry to refresh token",
    )

    # Database limits
    db_message_content_max_length: int = Field(
        default=1000,
        description="Max characters to store per message in audit log",
    )
    db_response_cleanup_days: int = Field(
        default=30,
        description="Days to keep responses before cleanup",
    )

    # Polling settings
    polling_max_backoff_level: int = Field(
        default=6,
        description="Max exponential backoff level (~64s max delay)",
    )
    polling_max_backoff_seconds: int = Field(
        default=60,
        description="Cap for backoff delay in seconds",
    )

    # Bookmarks display
    bookmarks_max_display_count: int = Field(
        default=10,
        description="Max bookmarks to show in query results",
    )
    bookmarks_text_preview_length: int = Field(
        default=100,
        description="Max characters to show per bookmark in list",
    )

    # URL knowledge base settings
    kb_content_dir: str = Field(
        default=".jarvis/url-saves",
        description="Directory containing saved markdown knowledge-base content",
    )
    kb_max_chunks_per_query: int = Field(
        default=6,
        description="Max retrieved chunks to include in grounded KB answers",
    )
    kb_rescan_stale_seconds: int = Field(
        default=300,
        description="Rescan KB content before retrieval when index age exceeds this threshold",
    )
    kb_chunk_size_chars: int = Field(
        default=1800,
        description="Maximum chunk size (in characters) for KB indexing",
    )

    vault_root: str = Field(
        default="vault",
        description="Root directory for local-first vault artifacts",
    )

    qmd_url: str = Field(
        default="http://localhost:8181",
        description="QMD MCP HTTP server URL",
    )
    qmd_enabled: bool = Field(
        default=False,
        description="Enable QMD hybrid search for /recall command",
    )
    qmd_timeout: float = Field(
        default=30.0,
        description="QMD HTTP request timeout in seconds",
    )
    qmd_search_limit: int = Field(
        default=5,
        description="Maximum number of QMD search results",
    )
    qmd_min_score: float = Field(
        default=0.2,
        description="Minimum QMD score threshold (0.0-1.0)",
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
            raise ValueError(f"polling_interval must be >= {MIN_POLLING_INTERVAL}s, got {v}")
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

    @field_validator("kb_content_dir")
    @classmethod
    def expand_kb_content_dir(cls, v: str) -> str:
        """Expand user home in KB content directory path."""
        return str(Path(v).expanduser())

    @field_validator("vault_root")
    @classmethod
    def expand_vault_root(cls, v: str) -> str:
        """Expand user home in vault root path."""
        return str(Path(v).expanduser())

    @field_validator("qmd_url")
    @classmethod
    def validate_qmd_url(cls, v: str) -> str:
        """Validate QMD URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError(f"QMD URL must start with http:// or https://, got: {v}")
        return v.rstrip("/")

    @field_validator("qmd_timeout")
    @classmethod
    def validate_qmd_timeout(cls, v: float) -> float:
        """Validate QMD timeout is reasonable."""
        if v <= 0 or v > QMD_MAX_TIMEOUT_SECONDS:
            raise ValueError(f"QMD timeout must be 0-{QMD_MAX_TIMEOUT_SECONDS}s, got {v}")
        return v

    @field_validator("qmd_search_limit")
    @classmethod
    def validate_qmd_search_limit(cls, v: int) -> int:
        """Validate QMD search limit is reasonable."""
        if v <= 0 or v > QMD_MAX_SEARCH_LIMIT:
            raise ValueError(f"QMD search limit must be 1-{QMD_MAX_SEARCH_LIMIT}, got {v}")
        return v

    @field_validator("qmd_min_score")
    @classmethod
    def validate_qmd_min_score(cls, v: float) -> float:
        """Validate QMD min score is in valid range."""
        if v < 0 or v > 1:
            raise ValueError(f"QMD min score must be 0.0-1.0, got {v}")
        return v

    @field_validator("kb_max_chunks_per_query", "kb_rescan_stale_seconds", "kb_chunk_size_chars")
    @classmethod
    def validate_positive_kb_values(cls, v: int) -> int:
        """Validate KB numeric settings are positive."""
        if v <= 0:
            raise ValueError(f"KB setting value must be positive, got {v}")
        return v

    @field_validator("x_api_base_url", "x_oauth_token_url")
    @classmethod
    def validate_https_url(cls, v: str) -> str:
        """Validate OAuth/API URLs use HTTPS for security."""
        if not v.startswith("https://"):
            raise ValueError(f"URL must use HTTPS for security, got: {v}")
        return v


def get_settings() -> Settings:
    """Get application settings singleton.

    Returns:
        Settings: Validated application settings.
    """
    return Settings()
