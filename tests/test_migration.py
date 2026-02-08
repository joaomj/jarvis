"""Quick test to verify jarvis migration works."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_command_router_integration():
    """Test that command router is properly integrated with JarvisBot."""
    from jarvis.command_router import route_command, BLOCKED_COMMANDS
    
    # Create mock bot
    mock_bot = MagicMock()
    mock_bot.opencode = AsyncMock()
    mock_bot.sessions = {}
    mock_bot._save_sessions = AsyncMock()
    
    # Test blocked command
    blocked_cmds = list(BLOCKED_COMMANDS.keys())
    for cmd in blocked_cmds[:2]:  # Test first 2 blocked commands
        handled, result = await route_command(cmd, "", 123, mock_bot)
        assert handled is True, f"Command /{cmd} should be handled locally"
        # result can be a string (error message) or list (response parts)
        result_str = result if isinstance(result, str) else str(result)
        assert "blocked" in result_str.lower() or "Not available" in result_str, \
            f"Blocked command /{cmd} should return error message"
        print(f"✓ /{cmd} correctly blocked")


@pytest.mark.asyncio
async def test_handlers_import():
    """Test that handlers can be imported."""
    from jarvis.handlers import handle_bridge_command, handle_intercept_command
    
    # Just verify imports work
    assert callable(handle_bridge_command)
    assert callable(handle_intercept_command)
    print("✓ Handler imports work")


def test_structured_logging():
    """Test that structured logging is configured."""
    from jarvis.logging_config import get_logger, configure_logging
    
    configure_logging("INFO")
    logger = get_logger("test")
    
    # Should not raise
    logger.info("Test message", test_key="test_value")
    print("✓ Structured logging works")


@pytest.mark.asyncio
async def test_new_session_command():
    """Test /new command creates session."""
    from jarvis.handlers.commands import handle_intercept_command
    
    # Create mock bot
    mock_bot = MagicMock()
    mock_bot.opencode = AsyncMock()
    mock_bot.opencode.create_session = AsyncMock(return_value="test-session-123")
    mock_bot.sessions = {}
    mock_bot._save_sessions = AsyncMock()
    
    # Test /new command
    result = await handle_intercept_command("new", "Test Session", 12345, mock_bot)
    
    # Verify session was created (jarvis uses keyword arg)
    mock_bot.opencode.create_session.assert_called_once_with(title="Test Session")
    assert "test-session-123" in result, "Result should contain new session ID"
    assert mock_bot.sessions[12345] == "test-session-123", "Session should be stored"
    print("✓ /new command works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
