"""Structured logging configuration using structlog.

Provides JSON-formatted logs with correlation IDs for observability.
"""

import logging
import sys
from typing import Any

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog with JSON formatting.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
    """
    # Configure standard library logging to use structlog processor
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level),
    )

    # Configure structlog
    structlog.configure(
        processors=[
            # Add correlation ID if present
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.ExtraAdder(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # JSON output for production
            structlog.processors.JSONRenderer()
            if log_level != "DEBUG"
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str, **context: Any) -> structlog.stdlib.BoundLogger:
    """Get a structured logger with optional context.
    
    Args:
        name: Logger name (usually __name__).
        **context: Additional context to bind to all log messages.
        
    Returns:
        BoundLogger: Structured logger instance.
        
    Example:
        >>> logger = get_logger(__name__, service="jarvis", version="0.1.0")
        >>> logger.info("bot_started", port=8080)
    """
    logger = structlog.get_logger(name)
    if context:
        logger = logger.bind(**context)
    return logger
