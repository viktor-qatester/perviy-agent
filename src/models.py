"""Event model and helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass
class Event:
    id: str
    type: str  # meetup | internship | conference
    title: str
    url: str
    source: str
    fetched_at: str
    date: str | None = None
    date_end: str | None = None
    location: str = ""
    tags: list[str] = field(default_factory=list)
    source_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        return cls(
            id=data["id"],
            type=data["type"],
            title=data["title"],
            url=data["url"],
            source=data["source"],
            fetched_at=data["fetched_at"],
            date=data.get("date"),
            date_end=data.get("date_end"),
            location=data.get("location", ""),
            tags=list(data.get("tags") or []),
            source_url=data.get("source_url") or data["url"],
        )


def dedupe_key(event: Event) -> tuple[str, str | None, str]:
    return (event.title.strip().lower(), event.date, event.url)


def is_upcoming(event: Event, today: date | None = None) -> bool:
    if not event.date:
        return True
    today = today or date.today()
    try:
        event_date = date.fromisoformat(event.date)
    except ValueError:
        return True
    return event_date >= today


def within_days(event: Event, days: int, today: date | None = None) -> bool:
    if not event.date:
        return False
    today = today or date.today()
    try:
        event_date = date.fromisoformat(event.date)
    except ValueError:
        return False
    delta = (event_date - today).days
    return 0 <= delta <= days
