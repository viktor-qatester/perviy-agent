"""Support-style FAQ over events (LLM + guardrails, keyword fallback)."""

from __future__ import annotations

import json
import logging

from src.config import settings
from src.llm.client import LLMError, events_to_json, get_llm_client
from src.llm.guardrails import check_support_answer
from src.llm.prompts import SUPPORT_SYSTEM
from src.models import Event, format_event_date, within_days

logger = logging.getLogger(__name__)

_SUPPORT_LIST_LIMIT = 10


def _prioritize_for_support(events: list[Event]) -> list[Event]:
    """Live vacancies first, then newest dated events.

    Collector stores dated events oldest-first and undated internships last
    (``date or "9999-99-99"``). The keyword FAQ only prints 10 rows, so that
    order hides still-open rabota.by / Habr listings behind older RSS posts.
    """
    vacancies: list[Event] = []
    dated: list[Event] = []
    other: list[Event] = []
    for event in events:
        if event.date:
            dated.append(event)
        elif event.type in ("internship", "vacancy"):
            vacancies.append(event)
        else:
            other.append(event)
    vacancies.sort(key=lambda e: e.fetched_at, reverse=True)
    dated.sort(key=lambda e: e.date or "", reverse=True)
    return vacancies + dated + other


def _keyword_answer(question: str, events: list[Event], days: int = 7) -> str:
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

    filtered = _prioritize_for_support(filtered)

    lines = ["Вот что нашёл (только из базы событий):", ""]
    for event in filtered[:_SUPPORT_LIST_LIMIT]:
        date_str = format_event_date(event)
        lines.append(f"• {event.title} — {date_str}")
        lines.append(f"  {event.url}")

    if len(filtered) > _SUPPORT_LIST_LIMIT:
        lines.append(f"\n…и ещё {len(filtered) - _SUPPORT_LIST_LIMIT} событий.")

    return "\n".join(lines)


def _llm_answer(question: str, events: list[Event]) -> str:
    client = get_llm_client(settings)
    if client is None:
        raise LLMError("LLM not configured")

    payload = json.dumps(
        {"question": question, "events": json.loads(events_to_json(events))},
        ensure_ascii=False,
        indent=2,
    )
    return client.complete(SUPPORT_SYSTEM, payload)


def answer(question: str, events: list[Event], days: int = 7) -> str:
    events = _prioritize_for_support(events)
    client = get_llm_client(settings)

    try:
        draft = _llm_answer(question, events)
        guard = check_support_answer(client, draft, events)
        if guard.safe:
            return draft

        logger.warning("Support guardrail blocked LLM answer: %s", guard.reason)
    except LLMError as exc:
        logger.warning("Support LLM fallback: %s", exc)

    return _keyword_answer(question, events, days=days)
