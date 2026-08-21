"""Build digest draft from events (LLM + template fallback)."""

from __future__ import annotations

import logging

from src.config import settings
from src.llm.client import LLMError, events_to_json, get_llm_client
from src.llm.prompts import DIGEST_SYSTEM
from src.models import Event, format_event_date, is_habr_career, is_rabota_by, is_telegram_rss, recently_fetched, recently_published, within_days

logger = logging.getLogger(__name__)


def _template_digest(events: list[Event], days: int) -> str:
    if not events:
        return (
            f"На ближайшие {days} дней новых событий не найдено.\n\n"
            "Черновик — требует подтверждения."
        )

    lines = [f"Дайджест IT-событий (Беларусь) на {days} дней:", ""]
    for event in events:
        date_str = format_event_date(event)
        loc = f", {event.location}" if event.location else ""
        lines.append(f"• [{event.type}] {event.title} — {date_str}{loc}")
        lines.append(f"  {event.url}")
        if event.tags:
            lines.append(f"  теги: {', '.join(event.tags)}")
        lines.append("")

    lines.append("Черновик — требует подтверждения.")
    return "\n".join(lines)


def _llm_digest(events: list[Event], days: int) -> str:
    client = get_llm_client(settings)
    if client is None:
        raise LLMError("LLM not configured")

    user = events_to_json(events)
    if not events:
        user = "[]"

    return client.complete(DIGEST_SYSTEM, user)


def build_digest(events: list[Event], days: int = 7) -> str:
    upcoming = [
        e
        for e in events
        if within_days(e, days)
        or (is_telegram_rss(e) and recently_published(e, days))
        or (is_rabota_by(e) and recently_fetched(e, days))
        or (is_habr_career(e) and recently_fetched(e, days))
    ]

    try:
        return _llm_digest(upcoming, days)
    except LLMError as exc:
        logger.warning("Digest LLM fallback: %s", exc)
        return _template_digest(upcoming, days)
