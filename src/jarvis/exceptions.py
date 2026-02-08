"""Custom exceptions for the OpenCode Telegram Bridge.

Provides structured error handling with specific exception types
for different failure modes.
"""


class BridgeError(Exception):
    """Base exception for all bridge errors."""

    pass


class OpenCodeError(BridgeError):
    """Error communicating with OpenCode API.

    Attributes:
        status_code: HTTP status code from OpenCode API (0 if not HTTP-related)
        message: Error message from OpenCode or generated description
    """

    def __init__(self, message: str, status_code: int = 0):
        self.status_code = status_code
        super().__init__(message)


class TelegramError(BridgeError):
    """Error communicating with Telegram API."""

    pass


class ConfigurationError(BridgeError):
    """Missing or invalid configuration."""

    pass


class CommandError(BridgeError):
    """Invalid command syntax or unknown command."""

    pass


class SessionError(BridgeError):
    """Session-related error (not found, invalid ID, etc.)."""

    pass


class ValidationError(BridgeError):
    """Input validation failed."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")
