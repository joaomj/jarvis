"""Command router for Jarvis Bot.

Maps Telegram commands to appropriate handlers:
- Pass through to OpenCode API (/compact, /undo, /models, /new, /sessions, etc.)
- Block (not available in Telegram: /exit, /editor, /themes)
- Bridge-native (/switch, /agent)
"""

from typing import TYPE_CHECKING

from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.bot import JarvisBot

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

# Bridge-native commands (handled by Jarvis, not OpenCode)
BRIDGE_NATIVE = {
    "switch",
    "agent",
}


async def route_command(
    command: str, arguments: str, user_id: int, bot: "JarvisBot"
) -> tuple[bool, list[dict[str, str]] | str]:
    """Route Telegram command to appropriate handler.

    Args:
        command: Command name (without /)
        arguments: Command arguments
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Tuple of (handled_locally, result)
        - If handled_locally=True: result is a response message string
        - If handled_locally=False: result is response parts from OpenCode
    """
    logger.info(
        "Routing command",
        command=command,
        arguments=arguments[:50] if arguments else "",
        user_id=user_id,
    )

    # Check blocked commands first
    if command in BLOCKED_COMMANDS:
        reason = BLOCKED_COMMANDS[command]
        logger.warning("Blocked command attempted", command=command, user_id=user_id)
        return (True, f"⚠️ Command /{command} is blocked.\n\n{reason}\n\nUse OpenCode TUI directly.")

    # Check bridge-native commands
    if command in BRIDGE_NATIVE:
        result = await _handle_bridge_native(command, arguments, user_id, bot)
        return (True, result)

    # All other commands pass through to OpenCode
    return (False, [])


async def _handle_bridge_native(cmd: str, args: str, user_id: int, bot: "JarvisBot") -> str:
    """Handle bridge-native commands.

    Args:
        cmd: Command name (switch, agent)
        args: Command arguments
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message for user
    """
    from jarvis.handlers.commands import handle_bridge_command  # noqa: PLC0415

    return await handle_bridge_command(cmd, args, user_id, bot)
