"""Support-style FAQ over events (no LLM in v0.1 — keyword routing)."""

from __future__ import annotations

from src.models import Event, within_days


def answer(question: str, events: list[Event], days: int = 7) -> str:
    q = question.lower().strip()

    if not any(k in q for k in ("митап", "meetup", "стажир", "intern", "конферен", "событ")):
        return (
            "Я отвечаю только про стажировки и митапы в Беларуси. "
            "Попробуйте, например: «митапы на этой неделе» или «стажировки qa»."
        )

    filtered = list(events)

    if "митап" in q or "meetup" in q:
        filtered = [e for e in filtered if e.type == "meetup"]
    elif "стажир" in q or "intern" in q:
        filtered = [e for e in filtered if e.type == "internship"]
    elif "конферен" in q:
        filtered = [e for e in filtered if e.type == "conference"]

    if "qa" in q:
        filtered = [e for e in filtered if "qa" in [t.lower() for t in e.tags]]

    if "python" in q or "питон" in q:
        filtered = [e for e in filtered if "python" in [t.lower() for t in e.tags]]

    if "недел" in q or "week" in q:
        filtered = [e for e in filtered if within_days(e, days)]

    if not filtered:
        return "В моей базе сейчас нет подходящих событий. Источники могли не обновиться."

    lines = ["Вот что нашёл (только из базы событий):", ""]
    for event in filtered[:10]:
        date_str = event.date or "дата уточняется"
        lines.append(f"• {event.title} — {date_str}")
        lines.append(f"  {event.url}")

    if len(filtered) > 10:
        lines.append(f"\n…и ещё {len(filtered) - 10} событий.")

    return "\n".join(lines)
