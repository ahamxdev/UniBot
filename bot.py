# bot.py
"""
Telegram Bot entry point.

This module:
  - Builds a single Application instance (PTB v20+)
  - Registers command/message/callback handlers
  - Starts lightweight background queue workers (for instant outbound sends)
  - Starts polling
"""

from __future__ import annotations

import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from tel_bot.config import TOKEN as BOT_TOKEN
from tel_bot.handlers import (
    start,
    handle_message,
    button_handler,
    start_message_queue_workers,  # ← NEW: worker-based queue
)


def configure_logging() -> None:
    """Configure basic logging for the bot process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    # Optional noise reduction:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def _post_init(app: Application) -> None:
    """
    Runs after the Application is built and the event loop is running.
    We start N queue workers here so messages are delivered immediately
    when they’re pushed to `message_queue`.
    """
    await start_message_queue_workers(app, workers=3)  # tune workers as needed


def build_application() -> Application:
    """
    Create and return the single Application instance.
    NOTE: Do NOT create multiple Application instances across your project.
    """
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Check tel_bot.config.TOKEN")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_post_init)  # ← important: start queue workers when loop is alive
        .build()
    )

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


def main() -> None:
    """Program entry point. Builds the app and starts polling."""
    configure_logging()
    app = build_application()
    logging.info("🤖 The robot is on!")
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
