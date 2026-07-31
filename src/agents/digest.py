"""Build digest draft from events (no LLM in v0.1 — template only)."""

from __future__ import annotations

from src.models import Event, within_days


def build_digest(events: list[Event], days: int = 7) -> str:
    upcoming = [e for e in events if within_days(e, days)]

    if not upcoming:
        return (
            f"На ближайшие {days} дней новых событий не найдено.\n\n"
            "Черновик — требует подтверждения."
        )

    lines = [f"Дайджест IT-событий (Беларусь) на {days} дней:", ""]
    for event in upcoming:
        date_str = event.date or "дата уточняется"
        loc = f", {event.location}" if event.location else ""
        lines.append(f"• [{event.type}] {event.title} — {date_str}{loc}")
        lines.append(f"  {event.url}")
        if event.tags:
            lines.append(f"  теги: {', '.join(event.tags)}")
        lines.append("")

    lines.append("Черновик — требует подтверждения.")
    return "\n".join(lines)
