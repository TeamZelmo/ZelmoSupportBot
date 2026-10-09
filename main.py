"""Entry point:  python main.py"""

import logging
import sys

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
import database
import handlers
import partner_manager


def setup_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        level=logging.INFO,
    )
    # Keep the bot token out of the logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def build_application() -> Application:
    application = Application.builder().token(config.BOT_TOKEN).build()

    private = filters.ChatType.PRIVATE

    # Commands
    application.add_handler(CommandHandler("start", handlers.start_command, filters=private))
    application.add_handler(CommandHandler("panel", handlers.partner_panel, filters=private))
    application.add_handler(CommandHandler("pending", handlers.pending_command, filters=private))

    # Reply conversation (must be registered before the generic text handler)
    reply_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.reply_callback, pattern=r"^reply:\d+$")],
        states={
            handlers.WAITING_REPLY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & private, handlers.send_partner_reply
                ),
            ],
        },
        fallbacks=[CommandHandler("cancel", handlers.cancel_reply, filters=private)],
        allow_reentry=True,
    )
    application.add_handler(reply_conversation)

    # Callback buttons
    application.add_handler(
        CallbackQueryHandler(
            handlers.status_callback, pattern=r"^status_(available|busy|offline)$"
        )
    )
    application.add_handler(
        CallbackQueryHandler(handlers.take_chat_callback, pattern=r"^take_chat:\d+$")
    )
    application.add_handler(
        CallbackQueryHandler(handlers.close_chat_callback, pattern=r"^close_chat:\d+$")
    )

    # Customer messages (any private non-command message)
    application.add_handler(
        MessageHandler(private & ~filters.COMMAND, handlers.customer_message)
    )

    application.add_error_handler(handlers.error_handler)
    return application


def main() -> None:
    setup_logging()
    logger = logging.getLogger("main")

    try:
        config.validate_config()
    except config.ConfigError as exc:
        print(f"\n{exc}\n\n.env file check karein (.env.example dekhein).", file=sys.stderr)
        sys.exit(1)

    try:
        database.init_database()
        partner_manager.register_configured_partners()
    except database.DatabaseError as exc:
        logger.error("Database start-up failed: %s", exc)
        sys.exit(1)

    application = build_application()
    logger.info("Bot started. Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
