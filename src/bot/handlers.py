"""Telegram bot handlers (support + HITL)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.agents.collector import CollectStats, collect
from src.agents.support import answer
from src.bot import pipeline
from src.bot.career_portals import build_internships_message, is_internships_request
from src.bot.state import BotState
from src.config import Settings
from src.notifiers.telegram import hitl_callback_data, parse_hitl_callback, _split_text
from src.sources.factory import build_sources

logger = logging.getLogger(__name__)

HELP_TEXT = """\
Первый Агент — IT-события BY

Команды:
/digest — собрать события и прислать черновик дайджеста
/internships — карьерные порталы и программы стажировок
/ask <вопрос> — support: митапы, стажировки
/help — эта справка

Или напишите «стажировки» — список порталов.
Вопросы: «митапы на этой неделе», «стажировки qa».

Черновик дайджеста: ✅ Опубликовать / ✏️ Править / ❌ Отмена
"""


def _authorized(update: Update, settings: Settings) -> bool:
    """Доступ только из личного чата TELEGRAM_CHAT_ID."""
    if update.effective_chat is None:
        return False
    allowed = settings.authorized_chat_id()
    if not allowed:
        return False
    return str(update.effective_chat.id) == allowed


async def _reject_unauthorized(update: Update) -> None:
    if update.effective_message:
        await update.effective_message.reply_text("Доступ запрещён.")


def _hitl_keyboard(nonce: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data=hitl_callback_data("approve", nonce)),
                InlineKeyboardButton("✏️ Править", callback_data=hitl_callback_data("edit", nonce)),
                InlineKeyboardButton("❌ Отмена", callback_data=hitl_callback_data("cancel", nonce)),
            ]
        ]
    )


def _load_state(settings: Settings) -> BotState:
    return BotState.load(settings.bot_state_file)


def _save_state(settings: Settings, state: BotState) -> None:
    state.save(settings.bot_state_file)


def _write_approval_log(settings: Settings, digest: str) -> Path:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = settings.logs_dir / f"approved-{stamp}.json"
    path.write_text(
        json.dumps(
            {
                "approved_at": datetime.now(timezone.utc).astimezone().isoformat(),
                "digest": digest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _format_digest_header(
    count: int,
    stats: CollectStats,
    errors: dict[str, str],
    *,
    scheduled: bool = False,
) -> str:
    prefix = "📅 Автоматический черновик дайджеста" if scheduled else "Черновик дайджеста"
    header = f"{prefix} ({count} событий, +{stats.added} новых)"
    if stats.refreshed:
        header += f", обновлено: {stats.refreshed}"
    if stats.skipped_duplicate:
        header += f", дублей пропущено: {stats.skipped_duplicate}"
    if errors:
        header += f"\n⚠ Ошибки источников: {errors}"
    return header


async def send_digest_draft(
    bot,
    chat_id: str,
    settings: Settings,
    *,
    scheduled: bool = False,
) -> None:
    """Collect events, build digest, send HITL draft to admin chat."""
    digest, count, errors, stats = pipeline.run_collect_and_digest(settings)

    state = _load_state(settings)
    nonce = state.set_pending(digest)
    _save_state(settings, state)

    header = _format_digest_header(count, stats, errors, scheduled=scheduled)
    body = f"{header}\n\n{digest}"
    chunks = _split_text(body, limit=4096)
    for index, chunk in enumerate(chunks):
        await bot.send_message(
            chat_id=chat_id,
            text=chunk,
            reply_markup=_hitl_keyboard(nonce) if index == len(chunks) - 1 else None,
            disable_web_page_preview=True,
        )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _authorized(update, settings):
        await _reject_unauthorized(update)
        return
    await update.message.reply_text(
        "Первый Агент на связи.\n\n"
        "Напишите /digest для черновика или /internships — порталы стажировок.\n"
        "/help — список команд."
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _authorized(update, settings):
        await _reject_unauthorized(update)
        return
    await update.message.reply_text(HELP_TEXT)


async def cmd_internships(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _authorized(update, settings):
        await _reject_unauthorized(update)
        return
    await _reply_internships(update, settings)


async def _reply_internships(update: Update, settings: Settings) -> None:
    message = build_internships_message(settings.career_portals_file)
    await update.message.reply_text(message, parse_mode="HTML", disable_web_page_preview=True)


async def cmd_digest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _authorized(update, settings):
        await _reject_unauthorized(update)
        return

    await update.message.reply_text("Собираю события…")
    await send_digest_draft(
        context.bot,
        str(update.effective_chat.id),
        settings,
    )


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _authorized(update, settings):
        await _reject_unauthorized(update)
        return

    question = " ".join(context.args).strip()
    if not question:
        await update.message.reply_text("Пример: /ask митапы на этой неделе")
        return

    await _reply_support(update, settings, question)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    if not _authorized(update, settings):
        await _reject_unauthorized(update)
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    state = _load_state(settings)
    if state.mode == "edit":
        nonce = state.set_pending(text)
        _save_state(settings, state)
        await update.message.reply_text(
            "Черновик обновлён. Проверьте и выберите действие:",
            reply_markup=_hitl_keyboard(nonce),
        )
        return

    if is_internships_request(text):
        await _reply_internships(update, settings)
        return

    await _reply_support(update, settings, text)


async def _reply_support(update: Update, settings: Settings, question: str) -> None:
    sources = build_sources(settings)
    events, _, _ = collect(sources, events_file=settings.events_file)
    reply = answer(question, events, days=settings.digest_days_ahead)
    await update.message.reply_text(reply)


async def _publish_digest_to_channel(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    channel_id: str,
    digest_text: str,
) -> None:
    for chunk in _split_text(digest_text, limit=4096):
        await context.bot.send_message(
            chat_id=channel_id,
            text=chunk,
            disable_web_page_preview=True,
        )


async def _reply_callback(query, text: str) -> None:
    if query.message is None:
        logger.warning("Callback has no message; cannot reply: %s", text)
        return
    await query.message.reply_text(text)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    query = update.callback_query
    if query is None:
        return

    if not _authorized(update, settings):
        await query.answer("Доступ запрещён.", show_alert=True)
        return

    await query.answer()
    parsed = parse_hitl_callback(query.data or "")
    if parsed is None:
        logger.warning("Unknown callback: %s", query.data)
        return

    action, nonce = parsed
    state = _load_state(settings)

    if not state.matches_hitl_nonce(nonce):
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            logger.debug("Could not remove stale HITL keyboard", exc_info=True)
        await _reply_callback(
            query,
            "Это кнопки от старого черновика. Используйте последнее сообщение или /digest.",
        )
        return

    if action == "cancel":
        state.clear_pending()
        _save_state(settings, state)
        await query.edit_message_reply_markup(reply_markup=None)
        await _reply_callback(query, "Черновик отменён.")
        return

    if action == "edit":
        state.start_edit()
        _save_state(settings, state)
        await _reply_callback(
            query,
            "Отправьте новый текст черновика одним сообщением.\n"
            "Или /digest — собрать заново из базы.",
        )
        return

    if action == "approve":
        digest_text = state.pending_digest
        log_path = _write_approval_log(settings, digest_text)
        state.clear_pending()
        _save_state(settings, state)
        await query.edit_message_reply_markup(reply_markup=None)

        channel_id = settings.publish_channel_id()
        if channel_id:
            try:
                await _publish_digest_to_channel(
                    context,
                    channel_id=channel_id,
                    digest_text=digest_text,
                )
            except Exception as exc:
                logger.exception("Channel publish failed")
                await _reply_callback(
                    query,
                    f"Черновик сохранён ({log_path.name}), но публикация в канал не удалась:\n{exc}",
                )
                return
            await _reply_callback(query, "✅ Черновик одобрен и опубликован в канал!")
            return

        await _reply_callback(
            query,
            f"✅ Черновик одобрен и сохранён.\n"
            f"Лог: {log_path.name}\n\n"
            "Задайте TELEGRAM_CHANNEL_ID для публикации в канал.",
        )
        return

    logger.warning("Unknown HITL action: %s", action)
