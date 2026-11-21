"""Undated manual_feed catalog rows must appear in the digest."""
from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from src.agents.collector import collect
from src.agents.digest import build_digest
from src.models import Event
from src.sources.manual_feed import ManualFeedSource


def _event(**overrides) -> Event:
    payload = dict(
        id="meetup-aston",
        type="meetup",
        title="ASTON — анонсы митапов и IT-событий",
        url="https://t.me/astonit",
        source="manual_feed",
        fetched_at="2026-07-31T13:00:00+03:00",
        date=None,
        location="Минск / online",
        tags=["meetup"],
        source_url="https://t.me/astonit",
    )
    payload.update(overrides)
    return Event(**payload)


class DigestManualCatalogTests(unittest.TestCase):
    def test_undated_manual_meetup_is_in_digest(self):
        meetup = _event()
        with patch("src.agents.digest.get_llm_client", return_value=None):
            digest = build_digest([meetup], days=7)
        self.assertIn(meetup.title, digest)
        self.assertIn(meetup.url, digest)
        self.assertIn("дата уточняется", digest)

    def test_past_dated_manual_meetup_stays_out_of_digest(self):
        past = (date.today() - timedelta(days=30)).isoformat()
        meetup = _event(date=past, title="Прошедший митап", url="https://example.com/old")
        with patch("src.agents.digest.get_llm_client", return_value=None):
            digest = build_digest([meetup], days=7)
        self.assertNotIn("Прошедший митап", digest)
        self.assertIn("новых событий не найдено", digest)

    def test_upcoming_dated_meetup_still_uses_calendar_window(self):
        soon = (date.today() + timedelta(days=2)).isoformat()
        meetup = _event(date=soon, title="Minsk Python Meetup 12", url="https://example.com/soon")
        with patch("src.agents.digest.get_llm_client", return_value=None):
            digest = build_digest([meetup], days=7)
        self.assertIn("Minsk Python Meetup 12", digest)
        self.assertIn(soon, digest)

    def test_real_manual_feed_collect_then_digest_includes_catalog_channels(self):
        source = ManualFeedSource(Path("data/manual_events.json"))
        events, errors, stats = collect([source])
        self.assertEqual(errors, {})
        self.assertGreaterEqual(stats.added, 1)
        with patch("src.agents.digest.get_llm_client", return_value=None):
            digest = build_digest(events, days=7)
        self.assertIn("ASTON — анонсы митапов и IT-событий", digest)
        self.assertIn("https://t.me/astonit", digest)
        self.assertIn("Minsk Python Meetup", digest)
        self.assertNotIn("новых событий не найдено", digest)


if __name__ == "__main__":
    unittest.main()
