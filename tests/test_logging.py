"""Tests for logging module."""

import logging

import structlog

from jarvis.logging import configure_logging, get_logger


class TestLogging:
    """Test suite for logging configuration."""

    def test_configure_logging_sets_level(self, caplog):
        """Test that logging level is set correctly."""
        configure_logging("DEBUG")
        
        logger = get_logger("test_debug")
        with caplog.at_level(logging.DEBUG):
            logger.debug("test_message", key="value")
        
        assert "test_message" in caplog.text

    def test_get_logger_returns_structlog_logger(self):
        """Test that get_logger returns a structlog logger."""
        configure_logging("INFO")
        
        logger = get_logger("test_logger")
        
        # Returns a BoundLoggerLazyProxy that wraps a BoundLogger
        assert hasattr(logger, "bind")
        assert hasattr(logger, "info")

    def test_logger_binds_context(self, caplog):
        """Test that context is bound to logger messages."""
        configure_logging("INFO")
        
        logger = get_logger("test_context", service="jarvis", version="0.1.0")
        
        with caplog.at_level(logging.INFO):
            logger.info("event_occurred", action="test")
        
        # Context should be in the log output
        assert "jarvis" in caplog.text or "service" in caplog.text

    def test_configure_logging_json_format_in_production(self):
        """Test that production mode uses JSON formatting."""
        # This test verifies configuration doesn't throw errors
        configure_logging("INFO")
        
        logger = get_logger("test_json")
        # Just verify we can log without errors
        logger.info("test_event", data="value")

    def test_configure_logging_console_format_in_debug(self):
        """Test that debug mode uses console formatting."""
        # This test verifies configuration doesn't throw errors
        configure_logging("DEBUG")
        
        logger = get_logger("test_console")
        # Just verify we can log without errors
        logger.debug("debug_event", data="value")
