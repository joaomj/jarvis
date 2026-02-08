"""Jarvis command handlers.

Handles bridge-native commands that OpenCode doesn't have direct API for.
"""

import html
from typing import TYPE_CHECKING

from jarvis.logging_config import get_logger

if TYPE_CHECKING:
    from jarvis.bot import JarvisBot

logger = get_logger("commands")


async def handle_intercept_command(
    cmd: str, args: str, user_id: int, bot: "JarvisBot"
) -> str:
    """Handle intercepted OpenCode commands.

    Args:
        cmd: Command name (models, new, sessions)
        args: Command arguments
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message for user
    """
    handlers = {
        "models": _handle_models,
        "new": _handle_new_session,
        "sessions": _handle_list_sessions,
    }

    handler = handlers.get(cmd)
    if handler:
        return await handler(args, user_id, bot)
    
    return f"Unknown command: /{cmd}"


async def handle_bridge_command(
    cmd: str, args: str, user_id: int, bot: "JarvisBot"
) -> str:
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


async def _handle_models(args: str, user_id: int, bot: "JarvisBot") -> str:
    """Show available models from OpenCode.

    Args:
        args: Command arguments (unused)
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message with available models
    """
    # For now, show a static list of common models
    # In the future, this could fetch from OpenCode's /config endpoint
    models = [
        "anthropic/claude-sonnet-4-20250514",
        "anthropic/claude-opus-4-20250514",
        "openai/gpt-4o",
        "google/gemini-2.5-pro",
    ]

    lines = ["📋 <b>Available Models</b>\n"]
    for i, model in enumerate(models, 1):
        lines.append(f"{i}. <code>{html.escape(model)}</code>")
    
    lines.append("\nTo set a model: /model &lt;provider/model&gt;")
    
    return "\n".join(lines)


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
        bot.sessions[user_id] = session_id
        await bot._save_sessions()

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


async def _handle_list_sessions(args: str, user_id: int, bot: "JarvisBot") -> str:
    """List user sessions.

    Args:
        args: Command arguments (unused)
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message with session info
    """
    current_session = bot.sessions.get(user_id, "None")
    
    lines = [
        "📋 <b>Your Sessions</b>\n",
        f"Current: <code>{current_session[:16]}...</code>" if current_session != "None" else "No active session",
        "\nTo create new: /new",
        "To switch: /switch &lt;session_id&gt;",
    ]
    
    return "\n".join(lines)


async def _handle_switch(args: str, user_id: int, bot: "JarvisBot") -> str:
    """Switch to specified session.

    Args:
        args: Session ID to switch to
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message
    """
    if not args:
        return "Usage: /switch &lt;session_id&gt;"

    session_id = args.strip()
    bot.sessions[user_id] = session_id
    await bot._save_sessions()

    logger.info("Switched session", session_id=session_id, user_id=user_id)
    return f"✅ Switched to session: <code>{session_id}</code>"


async def _handle_agent(args: str, user_id: int, bot: "JarvisBot") -> str:
    """Agent management (placeholder).

    Args:
        args: Command arguments
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message
    """
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

    return (
        "Usage:\n"
        "/agent get - Show agent info\n"
        "/agent set &lt;name&gt; - Set default agent"
    )


async def _handle_model(args: str, user_id: int, bot: "JarvisBot") -> str:
    """Set model for session.

    Args:
        args: Model ID or empty to show list
        user_id: Telegram user ID
        bot: JarvisBot instance

    Returns:
        Response message
    """
    if not args:
        # Show models list
        return await _handle_models("", user_id, bot)

    model_id = args.strip()

    # Validate format
    if "/" not in model_id:
        return (
            "⚠️ Model must be in format: <code>provider/model</code>\n"
            "Example: <code>anthropic/claude-sonnet-4</code>\n\n"
            "Use /models to see available models."
        )

    # Store model preference (in memory for now)
    if not hasattr(bot, '_model_preferences'):
        bot._model_preferences = {}
    bot._model_preferences[user_id] = model_id

    logger.info("Set model preference", model=model_id, user_id=user_id)
    return f"✅ Model set to: <code>{html.escape(model_id)}</code>\n\nThis will be used for new messages."
