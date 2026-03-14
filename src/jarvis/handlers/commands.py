"""Jarvis command handlers.

Handles bridge-native commands that OpenCode doesn't have direct API for.
"""

import html
from typing import TYPE_CHECKING

from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.bot import JarvisBot

logger = get_logger("commands")


async def handle_bridge_command(cmd: str, args: str, user_id: int, bot: "JarvisBot") -> str:
    """Handle bridge-native commands.

    Args:
        cmd: Command name (switch, agent)
        args: Command arguments
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message for user
    """
    handlers = {
        "switch": _handle_switch,
        "agent": _handle_agent,
    }

    handler = handlers.get(cmd)
    if handler:
        return await handler(args, user_id, bot)

    return f"Unknown bridge command: /{cmd}"


async def _handle_switch(args: str, user_id: int, bot: "JarvisBot") -> str:
    """Switch to specified session.

    Args:
        args: Session ID to switch to
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message
    """
    try:
        if not args:
            return "Usage: /switch &lt;session_id&gt;"

        session_id = args.strip()

        if bot.session_manager:
            if not bot.session_manager.is_session_owned_by_user(session_id, user_id):
                logger.warning(
                    "unauthorized_session_switch_attempt",
                    session_id=session_id,
                    user_id=user_id,
                )
                return "❌ Invalid session ID. You can only switch to your own sessions."

            bot.session_manager.set_session(user_id, session_id)

        logger.info("Switched session", session_id=session_id, user_id=user_id)
        return f"✅ Switched to session: <code>{html.escape(session_id)}</code>"
    except Exception as e:
        logger.error("_handle_switch_failed", error=str(e), exc_info=True)
        return "❌ Failed to switch session. Please try again."


async def _handle_agent(args: str, user_id: int, _bot: "JarvisBot") -> str:
    """Agent management (placeholder).

    Args:
        args: Command arguments
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message
    """
    try:
        if not args or args.lower() == "get":
            return (
                "🤖 <b>Agent Management</b>\n\n"
                "Agents are configured per-session in OpenCode.\n"
                "Use OpenCode TUI to change agents.\n\n"
                "Current session agents persist automatically."
            )

        if args.lower().startswith("set "):
            agent_name = args[4:].strip()
            logger.info("Agent change requested", agent=agent_name, user_id=user_id)
            return f"✅ Agent <code>{html.escape(agent_name)}</code> will be used for new sessions."

        return "Usage:\n/agent get - Show agent info\n/agent set &lt;name&gt; - Set default agent"
    except Exception as e:
        logger.error("_handle_agent_failed", error=str(e), exc_info=True)
        return "❌ Failed to process agent command. Please try again."
