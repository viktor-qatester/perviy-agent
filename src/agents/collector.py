"""Collect events from all sources."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.models import Event, dedupe_key, is_telegram_rss, is_upcoming, normalize_url
from src.sources.base import Source


@dataclass
class CollectStats:
    added: int = 0
    skipped_duplicate: int = 0
    skipped_past: int = 0
    kept_existing: int = 0
    pruned: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "added": self.added,
            "skipped_duplicate": self.skipped_duplicate,
            "skipped_past": self.skipped_past,
            "kept_existing": self.kept_existing,
            "pruned": self.pruned,
        }


def load_events(path: Path) -> list[Event]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Event.from_dict(item) for item in raw]


def _keep_in_storage(event: Event) -> bool:
    if is_telegram_rss(event):
        return True
    if event.date and not is_upcoming(event, date.today()):
        return False
    return True


def collect(
    sources: list[Source],
    *,
    events_file: Path | None = None,
) -> tuple[list[Event], dict[str, str], CollectStats]:
    """Fetch sources, merge with existing events.json, dedupe by URL and key."""
    existing = load_events(events_file) if events_file else []
    stats = CollectStats()
    errors: dict[str, str] = {}

    by_url: dict[str, Event] = {}
    seen_keys: set[tuple[str, str | None, str]] = set()

    for event in existing:
        url_key = normalize_url(event.url)
        if url_key in by_url:
            stats.skipped_duplicate += 1
            continue
        by_url[url_key] = event
        seen_keys.add(dedupe_key(event))
        stats.kept_existing += 1

    for source in sources:
        try:
            batch = source.fetch()
            for event in batch:
                url_key = normalize_url(event.url)
                key = dedupe_key(event)

                if url_key in by_url or key in seen_keys:
                    stats.skipped_duplicate += 1
                    continue

                if not is_telegram_rss(event) and event.date and not is_upcoming(event, date.today()):
                    stats.skipped_past += 1
                    continue

                by_url[url_key] = event
                seen_keys.add(key)
                stats.added += 1
        except Exception as exc:  # noqa: BLE001 — log source failure, do not invent data
            errors[source.name] = str(exc)

    merged = list(by_url.values())
    kept: list[Event] = []
    for event in merged:
        if _keep_in_storage(event):
            kept.append(event)
        else:
            stats.pruned += 1

    events = sorted(kept, key=lambda e: (e.date or "9999-99-99", e.title))
    return events, errors, stats


def save_events(path, events: list[Event]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [e.to_dict() for e in events]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
