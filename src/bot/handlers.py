"""Telegram bot handlers (support + HITL)."""

from __future__ import annotations

import asyncio
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
from src.notifiers.telegram import (
    HITL_CALLBACK_APPROVE,
    HITL_CALLBACK_CANCEL,
    HITL_CALLBACK_EDIT,
    _split_text,
)
from src.sources.factory import build_sources

logger = logging.getLogger(__name__)
_state_lock = asyncio.Lock()

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


def _hitl_keyboard(draft_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Опубликовать", callback_data=f"{HITL_CALLBACK_APPROVE}:{draft_id}"),
                InlineKeyboardButton("✏️ Править", callback_data=f"{HITL_CALLBACK_EDIT}:{draft_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"{HITL_CALLBACK_CANCEL}:{draft_id}"),
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

    async with _state_lock:
        state = _load_state(settings)
        if state.published_chunks:
            raise RuntimeError("Previous digest was partly published; retry approval first")
        state.set_pending(digest)
        _save_state(settings, state)

        header = _format_digest_header(count, stats, errors, scheduled=scheduled)
        body = f"{header}\n\n{digest}"
        chunks = _split_text(body, limit=4096)
        for index, chunk in enumerate(chunks):
            await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                reply_markup=_hitl_keyboard(state.draft_id) if index == len(chunks) - 1 else None,
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

    async with _state_lock:
        state = _load_state(settings)
        if state.mode == "edit":
            state.set_pending(text)
            _save_state(settings, state)
            await update.message.reply_text(
                "Черновик обновлён. Проверьте и выберите действие:",
                reply_markup=_hitl_keyboard(state.draft_id),
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
    state: BotState,
    settings: Settings,
) -> None:
    """Resume at the first chunk not yet confirmed by Telegram."""
    chunks = _split_text(state.pending_digest, limit=4096)
    for index in range(state.published_chunks, len(chunks)):
        await context.bot.send_message(
            chat_id=channel_id,
            text=chunks[index],
            disable_web_page_preview=True,
        )
        state.published_chunks = index + 1
        _save_state(settings, state)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.bot_data["settings"]
    query = update.callback_query
    if query is None:
        return

    if not _authorized(update, settings):
        await query.answer("Доступ запрещён.", show_alert=True)
        return

    async with _state_lock:
        state = _load_state(settings)
        raw = query.data or ""
        action, separator, draft_id = raw.rpartition(":")
        valid_actions = {
            HITL_CALLBACK_APPROVE,
            HITL_CALLBACK_EDIT,
            HITL_CALLBACK_CANCEL,
        }
        if (
            not separator
            or action not in valid_actions
            or not state.pending_digest
            or not state.draft_id
            or draft_id != state.draft_id
        ):
            await query.answer("Этот черновик уже не активен. Используйте /digest.", show_alert=True)
            return

        await query.answer()
        if action == HITL_CALLBACK_CANCEL:
            if state.published_chunks:
                await query.message.reply_text(
                    "Часть дайджеста уже опубликована. Повторите публикацию, чтобы закончить."
                )
                return
            state.clear_pending()
            _save_state(settings, state)
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("Черновик отменён.")
            return

        if action == HITL_CALLBACK_EDIT:
            if state.published_chunks:
                await query.message.reply_text(
                    "Часть дайджеста уже опубликована. Повторите публикацию, чтобы закончить."
                )
                return
            state.start_edit()
            _save_state(settings, state)
            await query.message.reply_text(
                "Отправьте новый текст черновика одним сообщением.\n"
                "Или /digest — собрать заново из базы."
            )
            return

        channel_id = settings.publish_channel_id()
        if not channel_id:
            await query.message.reply_text(
                "TELEGRAM_CHANNEL_ID не задан. Черновик сохранён; настройте канал и повторите."
            )
            return

        digest_text = state.pending_digest
        try:
            await _publish_digest_to_channel(
                context,
                channel_id=channel_id,
                state=state,
                settings=settings,
            )
        except Exception:
            logger.exception("Channel publish failed")
            await query.message.reply_text(
                "Публикация прервалась. Черновик и прогресс сохранены; "
                "нажмите ✅ ещё раз, чтобы продолжить."
            )
            return

        state.clear_pending()
        _save_state(settings, state)
        await query.edit_message_reply_markup(reply_markup=None)
        try:
            _write_approval_log(settings, digest_text)
        except OSError:
            logger.exception("Approved digest was published but approval log failed")
        await query.message.reply_text("✅ Черновик одобрен и опубликован в канал!")
