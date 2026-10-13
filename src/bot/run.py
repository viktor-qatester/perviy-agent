"""Run Telegram bot (long polling)."""

from __future__ import annotations

import logging
import re

from telegram import BotCommand
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from src.bot import handlers
from src.bot.schedule import setup_schedule
from src.config import Settings

logger = logging.getLogger(__name__)

# "<id>:<secret>" as in Telegram API URLs; ":" may also appear URL-encoded.
_TOKEN_RE = re.compile(r"\d{5,}(?::|%3[Aa])[A-Za-z0-9_-]{20,}")
_MIN_SECRET_LEN = 8
_known_secrets: set[str] = set()


def register_secret(value: str) -> None:
    """Also redact the exact configured token, whatever its format."""
    if value and len(value) >= _MIN_SECRET_LEN:
        _known_secrets.add(value)


def redact_token(text: str) -> str:
    for secret in _known_secrets:
        text = text.replace(secret, "<redacted>")
    return _TOKEN_RE.sub("<redacted>", text)


class TokenRedactingFilter(logging.Filter):
    """Telegram token is part of the API URL; keep it out of every log line."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_token(record.getMessage())
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = redact_token(record.exc_text)
        if record.stack_info:
            record.stack_info = redact_token(record.stack_info)
        return True


def configure_logging(secrets: tuple[str, ...] = ()) -> None:
    for secret in secrets:
        register_secret(secret)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    for noisy in ("httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, TokenRedactingFilter) for f in handler.filters):
            handler.addFilter(TokenRedactingFilter())


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
    configure_logging(secrets=(settings.telegram_bot_token,))
    try:
        app = build_application(settings)
        logger.info("Бот запущен (polling). Ctrl+C для остановки.")
        app.run_polling(drop_pending_updates=True)
    except Exception:
        # A rejected token raises InvalidToken("The token `<token>` was rejected ...")
        # at startup. The default traceback goes to stderr unfiltered, so log it
        # through the redacting handler and exit with a non-zero code instead.
        logger.critical("Бот остановлен из-за ошибки", exc_info=True)
        raise SystemExit(1) from None
