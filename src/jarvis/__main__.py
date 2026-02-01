"""Entry point for Jarvis Bot.

Starts the Telegram bot with webhook server.
"""

import asyncio
import signal
import sys

from aiohttp import web

from jarvis.bot import JarvisBot
from jarvis.config import get_settings
from jarvis.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def main() -> None:
    """Main entry point."""
    # Load configuration
    settings = get_settings()

    # Configure logging
    configure_logging(settings.log_level)

    logger.info(
        "jarvis_starting",
        env=settings.jarvis_env,
        log_level=settings.log_level,
    )

    # Create bot
    bot = JarvisBot(settings)

    try:
        # Initialize bot
        await bot.start()

        # Create and run web server
        runner = web.AppRunner(bot.webhook_app)
        await runner.setup()

        site = web.TCPSite(
            runner,
            host="0.0.0.0",
            port=settings.telegram_webhook_port,
        )
        await site.start()

        logger.info(
            "server_started",
            host="0.0.0.0",
            port=settings.telegram_webhook_port,
        )

        # Keep running until interrupted
        stop_event = asyncio.Event()

        def signal_handler(sig: int, frame: object) -> None:
            """Handle shutdown signals."""
            logger.info("shutdown_signal_received", signal=sig)
            stop_event.set()

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Wait for shutdown signal
        await stop_event.wait()

        # Cleanup
        logger.info("shutting_down")
        await bot.stop()
        await runner.cleanup()
        logger.info("shutdown_complete")

    except Exception as e:
        logger.error("fatal_error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
