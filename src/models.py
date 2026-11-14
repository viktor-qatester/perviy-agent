"""Event model and helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse


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
    return (event.title.strip().lower(), event.date, normalize_url(event.url))


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/")
    host = parsed.netloc.lower()
    return f"{parsed.scheme}://{host}{path}"


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


def recently_published(event: Event, days: int, today: date | None = None) -> bool:
    """Publication date within the last N days (for Telegram RSS posts)."""
    if not event.date:
        return True
    today = today or date.today()
    try:
        event_date = date.fromisoformat(event.date)
    except ValueError:
        return True
    age = (today - event_date).days
    return 0 <= age <= days


def is_telegram_rss(event: Event) -> bool:
    return event.source.startswith("telegram_rss:")


def is_rabota_by(event: Event) -> bool:
    return event.source.startswith("rabota_by:")


def is_habr_career(event: Event) -> bool:
    return event.source.startswith("habr_career:")


def is_open_vacancy(event: Event) -> bool:
    """Vacancy/internship without event date (e.g. rabota.by listing)."""
    return is_rabota_by(event) or is_habr_career(event) or event.type in ("internship", "vacancy")


def format_event_date(event: Event) -> str:
    """Human-readable date line for digest and support."""
    if event.date:
        return event.date
    if is_open_vacancy(event):
        return "🟢 Набор открыт"
    return "дата уточняется"


def recently_fetched(event: Event, days: int, today: date | None = None) -> bool:
    """True if event was collected within the last N days (by fetched_at)."""
    if not event.fetched_at:
        return False
    today = today or date.today()
    try:
        fetched = datetime.fromisoformat(event.fetched_at)
        fetched_day = fetched.date()
    except ValueError:
        return False
    age = (today - fetched_day).days
    return 0 <= age <= days


def in_digest_window(event: Event, days: int, today: date | None = None) -> bool:
    """True if the event belongs in a digest or «this week» support answer."""
    return (
        within_days(event, days, today)
        or (is_telegram_rss(event) and recently_published(event, days, today))
        or (is_rabota_by(event) and recently_fetched(event, days, today))
        or (is_habr_career(event) and recently_fetched(event, days, today))
    )
