"""Entry point for Jarvis Bot.

Starts the Telegram bot with polling.
"""

import asyncio
import signal
import sys

from jarvis.bot import JarvisBot
from jarvis.config import get_settings
from jarvis.logging_config import configure_logging, get_logger

logger = get_logger(__name__)


async def main() -> None:
    """Main entry point."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info(
        "jarvis_starting",
        env=settings.jarvis_env,
        log_level=settings.log_level,
    )

    bot = JarvisBot(settings)

    try:
        await bot.start()

        # Keep running until interrupted
        stop_event = asyncio.Event()

        def signal_handler(sig: int, frame: object) -> None:
            """Handle shutdown signals."""
            logger.info("shutdown_signal_received", signal=sig)
            bot.stop()
            stop_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        await stop_event.wait()

        logger.info("shutting_down")
        await bot.shutdown()
        logger.info("shutdown_complete")

    except Exception as e:
        logger.error("fatal_error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
