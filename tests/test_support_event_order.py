"""Support FAQ must not hide live vacancies behind older dated RSS posts."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from src.agents.collector import collect, save_events
from src.agents.support import answer
from src.models import Event


class _FakeSource:
    def __init__(self, name: str, events: list[Event]) -> None:
        self.name = name
        self._events = events

    def fetch(self) -> list[Event]:
        return list(self._events)


def _iso_days_ago(days: int) -> str:
    moment = datetime.now(timezone.utc) - timedelta(days=days)
    return moment.astimezone().isoformat(timespec="seconds")


def _rss_internship(*, days_ago: int, index: int) -> Event:
    pub = (date.today() - timedelta(days=days_ago)).isoformat()
    return Event(
        id=f"tg-belarusitwant-{index}",
        type="internship",
        title=f"Old RSS internship {index}",
        url=f"https://t.me/belarusitwant/{index}",
        source="telegram_rss:belarusitwant",
        fetched_at=_iso_days_ago(0),
        date=pub,
        location="Минск",
        tags=["qa", "internship"],
        source_url="https://t.me/belarusitwant",
    )


def _rabota_vacancy(*, title: str = "QA Intern (rabota.by)") -> Event:
    return Event(
        id="rabota-by-123",
        type="internship",
        title=title,
        url="https://rabota.by/vacancy/123",
        source="rabota_by:qa_junior",
        fetched_at=_iso_days_ago(0),
        date=None,
        location="Минск",
        tags=["qa", "internship"],
        source_url="https://rabota.by/vacancy/123",
    )


def _meetup(*, days_ago: int, title: str) -> Event:
    pub = (date.today() - timedelta(days=days_ago)).isoformat()
    return Event(
        id=f"tg-meetup-{title}",
        type="meetup",
        title=title,
        url=f"https://t.me/belarusitwant/{abs(hash(title)) % 10000}",
        source="telegram_rss:belarusitwant",
        fetched_at=_iso_days_ago(0),
        date=pub,
        location="Минск",
        tags=["meetup", "qa"],
        source_url="https://t.me/belarusitwant",
    )


class SupportEventOrderTests(unittest.TestCase):
    def test_internships_list_keeps_live_vacancy_when_rss_overflows_limit(self) -> None:
        # Collector order: 12 dated RSS internships first, undated vacancy last.
        rss = [_rss_internship(days_ago=20 - i, index=i) for i in range(12)]
        vacancy = _rabota_vacancy()
        events = sorted(
            [*rss, vacancy],
            key=lambda e: (e.date or "9999-99-99", e.title),
        )
        self.assertEqual(events[-1].url, vacancy.url)

        with patch("src.agents.support.get_llm_client", return_value=None):
            text = answer("стажировки qa", events, days=7)

        self.assertIn("QA Intern (rabota.by)", text)
        self.assertIn("https://rabota.by/vacancy/123", text)
        self.assertNotIn("Old RSS internship 0", text)

    def test_meetups_list_shows_newest_not_oldest(self) -> None:
        events = [
            _meetup(days_ago=20, title="Ancient Meetup"),
            _meetup(days_ago=1, title="Yesterday Meetup"),
        ]
        events = sorted(events, key=lambda e: (e.date or "9999-99-99", e.title))
        with patch("src.agents.support.get_llm_client", return_value=None):
            text = answer("митапы", events, days=7)
        self.assertIn("Yesterday Meetup", text)
        # Both fit in the 10-row cap; newest must still be listed.
        self.assertIn("Ancient Meetup", text)
        newest_pos = text.index("Yesterday Meetup")
        oldest_pos = text.index("Ancient Meetup")
        self.assertLess(newest_pos, oldest_pos)

    def test_collect_order_then_support_still_surfaces_vacancy(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        rss = [_rss_internship(days_ago=15 - i, index=i) for i in range(12)]
        vacancy = _rabota_vacancy(title="Live Habr-style Intern")
        vacancy.source = "habr_career:qa_remote_junior"
        vacancy.url = "https://career.habr.com/vacancies/999"
        vacancy.source_url = vacancy.url
        vacancy.id = "habr-career-999"

        with TemporaryDirectory() as tmp:
            events_file = Path(tmp) / "events.json"
            save_events(events_file, [])
            events, errors, _ = collect(
                [
                    _FakeSource("telegram_rss:belarusitwant", rss),
                    _FakeSource("habr_career:qa_remote_junior", [vacancy]),
                ],
                events_file=events_file,
            )

        self.assertEqual(errors, {})
        with patch("src.agents.support.get_llm_client", return_value=None):
            text = answer("стажировки", events, days=7)
        self.assertIn("Live Habr-style Intern", text)
        self.assertIn("https://career.habr.com/vacancies/999", text)


if __name__ == "__main__":
    unittest.main()
