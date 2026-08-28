"""Scheduled digest jobs (JobQueue / APScheduler)."""

from __future__ import annotations

import logging
from datetime import time
from zoneinfo import ZoneInfo

from telegram.ext import Application, ContextTypes

from src.bot.handlers import send_digest_draft
from src.config import Settings

logger = logging.getLogger(__name__)

# python-telegram-bot JobQueue.run_daily (v20+): 0=Sunday … 6=Saturday.
# This is NOT datetime.weekday() (Monday=0). Passing Python weekdays would
# fire the digest one calendar day early (default tue,fri → Mon+Thu).
_WEEKDAY_ALIASES: dict[str, int] = {
    "sun": 0,
    "sunday": 0,
    "mon": 1,
    "monday": 1,
    "tue": 2,
    "tuesday": 2,
    "wed": 3,
    "wednesday": 3,
    "thu": 4,
    "thursday": 4,
    "fri": 5,
    "friday": 5,
    "sat": 6,
    "saturday": 6,
}


def parse_schedule_days(raw: str) -> tuple[int, ...]:
    days: list[int] = []
    for part in raw.split(","):
        key = part.strip().lower()
        if not key:
            continue
        if key not in _WEEKDAY_ALIASES:
            raise ValueError(f"Unknown weekday in SCHEDULE_DAYS: {part.strip()!r}")
        days.append(_WEEKDAY_ALIASES[key])
    if not days:
        raise ValueError("SCHEDULE_DAYS is empty")
    return tuple(sorted(set(days)))


def parse_schedule_time(raw: str) -> time:
    parts = raw.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid SCHEDULE_TIME: {raw!r} (expected HH:MM)")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid SCHEDULE_TIME: {raw!r}")
    return time(hour=hour, minute=minute)


async def scheduled_digest_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    chat_id = settings.authorized_chat_id()
    if not chat_id:
        logger.error("Scheduled digest skipped: TELEGRAM_CHAT_ID is not set")
        return

    logger.info("Scheduled digest: starting collect pipeline")
    try:
        await send_digest_draft(
            context.bot,
            chat_id,
            settings,
            scheduled=True,
        )
    except Exception:
        logger.exception("Scheduled digest failed")
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠ Ошибка автоматического сбора дайджеста. Проверьте логи бота.",
        )


def setup_schedule(app: Application, settings: Settings) -> None:
    if not settings.schedule_enabled:
        logger.info("Schedule disabled (SCHEDULE_ENABLED=false)")
        return

    if app.job_queue is None:
        logger.warning(
            "JobQueue unavailable. Install: pip install \"python-telegram-bot[job-queue]\""
        )
        return

    try:
        days = parse_schedule_days(settings.schedule_days)
        run_time = parse_schedule_time(settings.schedule_time)
        tz = ZoneInfo(settings.timezone)
    except (ValueError, KeyError) as exc:
        logger.error("Invalid schedule config: %s", exc)
        return

    app.job_queue.run_daily(
        scheduled_digest_job,
        time=run_time.replace(tzinfo=tz),
        days=days,
        name="scheduled_digest",
    )
    logger.info(
        "Schedule enabled: %s at %s (%s), days=%s",
        settings.schedule_days,
        settings.schedule_time,
        settings.timezone,
        days,
    )
