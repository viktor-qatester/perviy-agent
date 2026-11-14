"""Support «this week» must use the same window as the digest."""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from src.agents.digest import build_digest
from src.agents.support import answer
from src.llm.client import LLMError
from src.models import Event, in_digest_window


def _iso_days_ago(days: int) -> str:
    moment = datetime.now(timezone.utc) - timedelta(days=days)
    return moment.astimezone().isoformat(timespec="seconds")


def _telegram_meetup(*, days_ago: int, title: str = "QA Meetup Minsk") -> Event:
    pub = (date.today() - timedelta(days=days_ago)).isoformat()
    return Event(
        id="tg-belarusitwant-1",
        type="meetup",
        title=title,
        url="https://t.me/belarusitwant/1",
        source="telegram_rss:belarusitwant",
        fetched_at=_iso_days_ago(0),
        date=pub,
        location="Минск",
        tags=["meetup", "qa"],
        source_url="https://t.me/belarusitwant",
    )


def _rabota_vacancy(*, fetched_days_ago: int, title: str = "QA Intern") -> Event:
    return Event(
        id="rabota-by-123",
        type="internship",
        title=title,
        url="https://rabota.by/vacancy/123",
        source="rabota_by:qa_junior",
        fetched_at=_iso_days_ago(fetched_days_ago),
        date=None,
        location="Минск",
        tags=["qa", "internship"],
        source_url="https://rabota.by/vacancy/123",
    )


def _future_meetup(*, days_ahead: int, title: str = "Python Meetup") -> Event:
    return Event(
        id="meetup-future",
        type="meetup",
        title=title,
        url="https://example.com/meetup",
        source="manual_feed",
        fetched_at=_iso_days_ago(0),
        date=(date.today() + timedelta(days=days_ahead)).isoformat(),
        location="Минск",
        tags=["meetup", "python"],
        source_url="https://example.com/meetup",
    )


class DigestWindowTests(unittest.TestCase):
    def test_recent_rss_and_vacancy_are_in_window(self) -> None:
        self.assertTrue(in_digest_window(_telegram_meetup(days_ago=2), 7))
        self.assertTrue(in_digest_window(_rabota_vacancy(fetched_days_ago=0), 7))
        self.assertTrue(in_digest_window(_future_meetup(days_ahead=3), 7))

    def test_stale_rss_and_vacancy_are_out_of_window(self) -> None:
        self.assertFalse(in_digest_window(_telegram_meetup(days_ago=20), 7))
        self.assertFalse(in_digest_window(_rabota_vacancy(fetched_days_ago=10), 7))


class SupportWeekWindowTests(unittest.TestCase):
    def test_meetups_this_week_includes_recent_telegram_rss(self) -> None:
        stale = _telegram_meetup(days_ago=20, title="Old Meetup")
        stale.id = "tg-old"
        stale.url = "https://t.me/belarusitwant/99"
        events = [_telegram_meetup(days_ago=2), stale]
        with patch("src.agents.support.get_llm_client", return_value=None):
            text = answer("митапы на этой неделе", events, days=7)
        self.assertIn("QA Meetup Minsk", text)
        self.assertNotIn("Old Meetup", text)
        self.assertNotIn("нет подходящих событий", text)

    def test_internships_this_week_includes_fresh_vacancies(self) -> None:
        stale = _rabota_vacancy(fetched_days_ago=10, title="Stale Intern")
        stale.id = "rabota-by-999"
        stale.url = "https://rabota.by/vacancy/999"
        stale.source_url = stale.url
        events = [_rabota_vacancy(fetched_days_ago=0, title="QA Intern"), stale]
        with patch("src.agents.support.get_llm_client", return_value=None):
            text = answer("стажировки на этой неделе", events, days=7)
        self.assertIn("QA Intern", text)
        self.assertNotIn("Stale Intern", text)
        self.assertNotIn("нет подходящих событий", text)

    def test_digest_and_support_agree_on_live_events(self) -> None:
        events = [
            _telegram_meetup(days_ago=1),
            _rabota_vacancy(fetched_days_ago=0),
            _future_meetup(days_ahead=2),
        ]
        with patch("src.agents.digest._llm_digest", side_effect=LLMError("disabled")):
            digest = build_digest(events, days=7)
        with patch("src.agents.support.get_llm_client", return_value=None):
            meetups = answer("митапы на этой неделе", events, days=7)
            internships = answer("стажировки на этой неделе", events, days=7)
        self.assertIn("QA Meetup Minsk", digest)
        self.assertIn("QA Meetup Minsk", meetups)
        self.assertIn("QA Intern", digest)
        self.assertIn("QA Intern", internships)
        self.assertIn("Python Meetup", digest)
        self.assertIn("Python Meetup", meetups)


if __name__ == "__main__":
    unittest.main()
