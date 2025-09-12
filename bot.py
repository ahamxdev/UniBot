# bot.py
"""
Telegram Bot entry point.

This module:
  - Builds a single Application instance (PTB v20+)
  - Registers command/message/callback handlers
  - Attaches the repeating job that drains the outbound message queue
  - Starts polling

Handlers and the message-queue job are defined in `tel_bot.handlers`.
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
    setup_message_queue_job,
)


def configure_logging() -> None:
    """
    Configure basic logging for the bot process.
    Adjust the level/format as needed. In production,
    you might want INFO or WARNING instead of DEBUG.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    # Reduce noisy logs from underlying libraries if desired:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def build_application() -> Application:
    """
    Create and return the single Application instance.

    NOTE:
    - Do NOT create multiple Application instances across your project.
      JobQueue and handlers must be attached to the same instance that runs polling.
    """
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing. Check tel_bot.config.TOKEN")

    app = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Attach the repeating job to drain the message queue
    setup_message_queue_job(app)

    return app


def main() -> None:
    """
    Program entry point. Builds the app and starts polling.
    """
    configure_logging()
    app = build_application()

    logging.info("🤖 The robot is on!")
    # close_loop=False keeps the event loop available for other tasks if needed.
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
