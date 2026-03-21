"""Command router for Jarvis Bot.

Maps Telegram commands to appropriate handlers:
- Pass through to OpenCode API (all commands)
- Block (not available in Telegram: /exit, /editor, /themes)
"""

from jarvis.logging_config import get_logger

logger = get_logger("command_router")

# Commands blocked in Telegram (require TUI)
BLOCKED_COMMANDS = {
    "exit": "Exit requires the TUI interface",
    "quit": "Exit requires the TUI interface",
    "q": "Exit requires the TUI interface",
    "editor": "External editor not available in Telegram",
    "themes": "Theme switching requires the TUI interface",
    "theme": "Theme switching requires the TUI interface",
}


def is_command_blocked(command: str) -> str | None:
    """Check if a command should be blocked.

    Args:
        command: Command name (without /)

    Returns:
        Block reason if blocked, None if allowed
    """
    logger.info(
        "Checking command",
        command=command,
    )

    if command in BLOCKED_COMMANDS:
        reason = BLOCKED_COMMANDS[command]
        logger.warning("Blocked command attempted", command=command)
        return f"⚠️ Command /{command} is blocked.\n\n{reason}\n\nUse OpenCode TUI directly."

    return None
