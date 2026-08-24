"""Collector must refresh still-listed vacancies so digest does not drop them."""

from __future__ import annotations

import json
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.agents.collector import collect, save_events
from src.agents.digest import build_digest
from src.llm.client import LLMError
from src.models import Event


class _FakeSource:
    def __init__(self, name: str, events: list[Event]) -> None:
        self.name = name
        self._events = events

    def fetch(self) -> list[Event]:
        return list(self._events)


def _vacancy(*, fetched_at: str, title: str = "QA Intern") -> Event:
    return Event(
        id="rabota-by-123",
        type="internship",
        title=title,
        url="https://rabota.by/vacancy/123",
        source="rabota_by:qa_junior",
        fetched_at=fetched_at,
        date=None,
        location="Минск",
        tags=["qa", "internship"],
        source_url="https://rabota.by/vacancy/123",
    )


def _iso_days_ago(days: int) -> str:
    moment = datetime.now(timezone.utc) - timedelta(days=days)
    return moment.astimezone().isoformat(timespec="seconds")


class CollectorRefreshTests(unittest.TestCase):
    def test_refetch_updates_fetched_at_and_title(self) -> None:
        old = _vacancy(fetched_at=_iso_days_ago(10), title="QA Intern (old)")
        fresh = _vacancy(fetched_at=_iso_days_ago(0), title="QA Intern (updated)")

        with TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "events.json"
            save_events(events_file, [old])

            events, errors, stats = collect(
                [_FakeSource("rabota_by:qa_junior", [fresh])],
                events_file=events_file,
            )

        self.assertEqual(errors, {})
        self.assertEqual(stats.added, 0)
        self.assertEqual(stats.refreshed, 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "QA Intern (updated)")
        self.assertEqual(events[0].fetched_at, fresh.fetched_at)

    def test_digest_keeps_open_vacancy_after_week_if_still_listed(self) -> None:
        stale = _vacancy(fetched_at=_iso_days_ago(10))
        live = _vacancy(fetched_at=_iso_days_ago(0))

        with TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "events.json"
            save_events(events_file, [stale])
            with patch("src.agents.digest._llm_digest", side_effect=LLMError("disabled")):
                dropped = build_digest([stale], days=7)
            events, _, _ = collect(
                [_FakeSource("rabota_by:qa_junior", [live])],
                events_file=events_file,
            )
            with patch("src.agents.digest._llm_digest", side_effect=LLMError("disabled")):
                digest = build_digest(events, days=7)

        self.assertIn("На ближайшие 7 дней новых событий не найдено", dropped)
        self.assertIn("QA Intern", digest)
        self.assertIn("https://rabota.by/vacancy/123", digest)

    def test_vacancy_not_in_latest_fetch_is_not_refreshed(self) -> None:
        stale = _vacancy(fetched_at=_iso_days_ago(10))
        other = Event(
            id="rabota-by-999",
            type="internship",
            title="Other Intern",
            url="https://rabota.by/vacancy/999",
            source="rabota_by:qa_junior",
            fetched_at=_iso_days_ago(0),
            date=None,
            location="Минск",
            tags=["qa"],
            source_url="https://rabota.by/vacancy/999",
        )

        with TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "events.json"
            save_events(events_file, [stale])
            events, _, stats = collect(
                [_FakeSource("rabota_by:qa_junior", [other])],
                events_file=events_file,
            )

        by_url = {e.url: e for e in events}
        self.assertEqual(stats.refreshed, 0)
        self.assertEqual(stats.added, 1)
        self.assertEqual(by_url[stale.url].fetched_at, stale.fetched_at)


class SaveEventsRoundtripTests(unittest.TestCase):
    def test_save_and_load_preserves_fields(self) -> None:
        event = _vacancy(fetched_at=_iso_days_ago(0))
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.json"
            save_events(path, [event])
            raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(raw[0]["url"], event.url)
        self.assertEqual(date.fromisoformat(raw[0]["fetched_at"][:10]), date.today())


if __name__ == "__main__":
    unittest.main()
