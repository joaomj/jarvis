"""Structured logging configuration with trace_id support.

Provides JSON-formatted logs with trace context for debugging
distributed operations across Telegram and OpenCode APIs.
"""

import logging
import uuid
from contextvars import ContextVar

import orjson
import structlog

# Context variable for trace ID propagation across async boundaries
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    """Get current trace ID or generate new one.

    Returns:
        Current trace ID from context, or newly generated UUID
    """
    try:
        return trace_id_var.get()
    except LookupError:
        return str(uuid.uuid4())


def set_trace_id(trace_id: str | None = None) -> str:
    """Set trace ID in context for current async operation.

    Args:
        trace_id: Trace ID to set, or None to generate new

    Returns:
        The trace ID that was set
    """
    tid = trace_id or str(uuid.uuid4())
    trace_id_var.set(tid)
    return tid


def clear_trace_id() -> None:
    """Clear trace ID from context."""
    try:
        trace_id_var.set("")
    except LookupError:
        pass


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for JSON structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(serializer=orjson.dumps),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=None,
        level=level,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get structured logger with service context.

    Args:
        name: Component name (e.g., 'telegram', 'opencode', 'bridge')

    Returns:
        Configured structlog logger with service context
    """
    return structlog.get_logger(service="jarvis", component=name)


# Convenience function for logging with trace context
def log_with_trace(
    logger: structlog.stdlib.BoundLogger,
    level: str,
    message: str,
    **kwargs,
) -> None:
    """Log message with automatic trace_id inclusion.

    Args:
        logger: Structlog logger instance
        level: Log level (debug, info, warning, error)
        message: Log message
        **kwargs: Additional context fields
    """
    method = getattr(logger, level.lower())
    method(message, trace_id=get_trace_id(), **kwargs)
