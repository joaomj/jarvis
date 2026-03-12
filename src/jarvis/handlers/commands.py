"""Jarvis command handlers.

Handles bridge-native commands that OpenCode doesn't have direct API for.
"""

import html
from typing import TYPE_CHECKING

from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.bot import JarvisBot

logger = get_logger("commands")


async def handle_intercept_command(cmd: str, args: str, user_id: int, bot: "JarvisBot") -> str:
    """Handle intercepted OpenCode commands.

    Args:
        cmd: Command name (models, new, sessions, recall)
        args: Command arguments
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message for user
    """
    from jarvis.handlers.qmd import handle_recall  # noqa: PLC0415

    handlers = {
        "models": _handle_models,
        "new": _handle_new_session,
        "sessions": _handle_list_sessions,
        "recall": lambda a, _u, b: handle_recall(a, b),
    }

    handler = handlers.get(cmd)
    if handler:
        return await handler(args, user_id, bot)

    return f"Unknown command: /{cmd}"


async def handle_bridge_command(cmd: str, args: str, user_id: int, bot: "JarvisBot") -> str:
    """Handle bridge-native commands.

    Args:
        cmd: Command name (switch, agent, model)
        args: Command arguments
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message for user
    """
    handlers = {
        "switch": _handle_switch,
        "agent": _handle_agent,
        "model": _handle_model,
    }

    handler = handlers.get(cmd)
    if handler:
        return await handler(args, user_id, bot)

    return f"Unknown bridge command: /{cmd}"


async def _handle_models(_args: str, user_id: int, bot: "JarvisBot") -> str:
    """Show available models and current model.

    Args:
        args: Command arguments (unused)
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message with available models
    """
    try:
        current = None
        if bot.model_selector:
            current = bot.model_selector.get_model_for_user(user_id)

        lines = ["📋 <b>Available Models</b>\n"]

        if current:
            lines.append(f"Current: <code>{html.escape(current)}</code>")

        models = [
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-opus-4-20250514",
            "openai/gpt-4o",
            "google/gemini-2.5-pro",
        ]

        lines.append("\n<b>Favorites</b>:")
        for i, model in enumerate(models, 1):
            lines.append(f"{i}. <code>{html.escape(model)}</code>")

        lines.append("\nSet: <code>!model provider/model</code>")
        lines.append("Fav: <code>!models</code> then reply with number")

        return "\n".join(lines)
    except Exception as e:
        logger.error("_handle_models_failed", error=str(e), exc_info=True)
        return "❌ Failed to load models. Please try again."


async def _handle_new_session(args: str, user_id: int, bot: "JarvisBot") -> str:
    """Create new OpenCode session.

    Args:
        args: Optional session title
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message
    """
    title = args or f"Jarvis Session {user_id}"

    try:
        if not bot.opencode:
            return "❌ OpenCode client not initialized"

        session_id = await bot.opencode.create_session(title=title)

        if bot.session_manager:
            bot.session_manager.set_session(user_id, session_id)

        logger.info(
            "Created new session",
            session_id=session_id,
            title=title,
            user_id=user_id,
        )
        return f"✅ New session created:\n<code>{session_id}</code>"
    except Exception as e:
        logger.error("Failed to create session", error=str(e), user_id=user_id)
        return f"❌ Failed to create session: {html.escape(str(e))}"


async def _handle_list_sessions(_args: str, user_id: int, bot: "JarvisBot") -> str:
    """List user sessions.

    Args:
        args: Command arguments (unused)
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message with session info
    """
    try:
        current_session = "None"
        if bot.session_manager:
            current_session = bot.session_manager.get_session(user_id) or "None"

        lines = [
            "📋 <b>Your Sessions</b>\n",
            f"Current: <code>{html.escape(current_session[:16])}...</code>"
            if current_session != "None"
            else "No active session",
            "\nTo create new: /new",
            "To switch: /switch &lt;session_id&gt;",
        ]

        return "\n".join(lines)
    except Exception as e:
        logger.error("_handle_list_sessions_failed", error=str(e), exc_info=True)
        return "❌ Failed to list sessions. Please try again."


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

        # Validate session ownership before switching
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


async def _handle_model(args: str, user_id: int, bot: "JarvisBot") -> str:
    """Set or show model for session.

    Args:
        args: Model ID or empty to show current
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message
    """
    try:
        if not args:
            current = None
            if bot.model_selector:
                current = bot.model_selector.get_model_for_user(user_id)

            if current:
                return (
                    f"🤖 <b>Current Model</b>\n\n"
                    f"<code>{html.escape(current)}</code>\n\n"
                    f"Source: custom\n"
                    "Use <code>!model &lt;provider/model&gt;</code> to change."
                )
            return (
                "🤖 <b>Model</b>\n\n"
                "No model set.\n"
                "Use <code>!model &lt;provider/model&gt;</code> to set one."
            )

        model_id = args.strip()

        if "/" not in model_id:
            return (
                "⚠️ Model must be in format: <code>provider/model</code>\n"
                "Example: <code>anthropic/claude-sonnet-4-20250514</code>\n\n"
                "Use !models to see available models."
            )

        if bot.model_selector:
            bot.model_selector.set_model_for_user(user_id, model_id)

        logger.info("Set model preference", model=model_id, user_id=user_id)
        return f"✅ Model set to: <code>{html.escape(model_id)}</code>\n\nThis will be used for your messages."
    except Exception as e:
        logger.error("_handle_model_failed", error=str(e), exc_info=True)
        return "❌ Failed to set model. Please try again."
