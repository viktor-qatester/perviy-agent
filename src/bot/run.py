"""Run Telegram bot (long polling)."""

from __future__ import annotations

import logging

from telegram import BotCommand
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from src.bot import handlers
from src.bot.schedule import setup_schedule
from src.config import Settings

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand("start", "Начало работы"),
    BotCommand("help", "Справка по командам"),
    BotCommand("digest", "Черновик дайджеста"),
    BotCommand("internships", "Порталы стажировок"),
    BotCommand("ask", "Вопрос support"),
]


async def _post_init(app: Application) -> None:
    settings: Settings = app.bot_data["settings"]
    await app.bot.set_my_commands(BOT_COMMANDS)
    setup_schedule(app, settings)


def build_application(settings: Settings) -> Application:
    if not settings.telegram_bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан в .env")

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .build()
    )
    app.bot_data["settings"] = settings

    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("help", handlers.cmd_help))
    app.add_handler(CommandHandler("digest", handlers.cmd_digest))
    app.add_handler(CommandHandler("internships", handlers.cmd_internships))
    app.add_handler(CommandHandler("ask", handlers.cmd_ask))
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))

    return app


def run_bot(settings: Settings) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    app = build_application(settings)
    logger.info("Бот запущен (polling). Ctrl+C для остановки.")
    app.run_polling(drop_pending_updates=True)
