"""Collect events from all sources."""

from __future__ import annotations

import json
from datetime import date

from src.models import Event, dedupe_key, is_upcoming
from src.sources.base import Source


def collect(sources: list[Source]) -> tuple[list[Event], dict[str, str]]:
    """Return deduplicated upcoming events and per-source errors."""
    seen: set[tuple[str, str | None, str]] = set()
    events: list[Event] = []
    errors: dict[str, str] = {}

    for source in sources:
        try:
            batch = source.fetch()
            for event in batch:
                key = dedupe_key(event)
                if key in seen:
                    continue
                if not is_upcoming(event, date.today()):
                    continue
                seen.add(key)
                events.append(event)
        except Exception as exc:  # noqa: BLE001 — log source failure, do not invent data
            errors[source.name] = str(exc)

    events.sort(key=lambda e: (e.date or "9999-99-99", e.title))
    return events, errors


def save_events(path, events: list[Event]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [e.to_dict() for e in events]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
