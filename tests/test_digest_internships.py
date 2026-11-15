"""Open internships must survive collect and appear in the digest."""
from __future__ import annotations

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.agents.collector import collect, save_events
from src.agents.digest import build_digest
from src.models import Event, format_event_date


def _event(**overrides) -> Event:
    past = (date.today() - timedelta(days=90)).isoformat()
    payload = dict(
        id="manual-qa-intern",
        type="internship",
        title="Стажировки QA / тестирование (rabota.by)",
        url="https://rabota.by/stazhirovki?q=QA",
        source="manual_feed",
        fetched_at=f"{past}T13:00:00+03:00",
        date=past,
        location="Минск",
        tags=["internship", "qa"],
        source_url="https://rabota.by/stazhirovki",
    )
    payload.update(overrides)
    return Event(**payload)


class DigestInternshipTests(unittest.TestCase):
    def test_collect_keeps_past_dated_internship_but_prunes_past_meetup(self):
        past_meetup = _event(
            id="old-meetup",
            type="meetup",
            title="Прошедший митап",
            url="https://example.com/meetup",
            source="manual_feed",
        )
        source = SimpleNamespace(name="manual_feed", fetch=lambda: [_event(), past_meetup])
        with tempfile.TemporaryDirectory() as temp:
            events_file = Path(temp) / "events.json"
            events, errors, stats = collect([source], events_file=events_file)

        self.assertEqual(errors, {})
        titles = [event.title for event in events]
        self.assertIn("Стажировки QA / тестирование (rabota.by)", titles)
        self.assertNotIn("Прошедший митап", titles)
        self.assertEqual(stats.skipped_past, 1)

    def test_digest_includes_stale_manual_internship_catalog(self):
        internship = _event()
        with patch("src.agents.digest.get_llm_client", return_value=None):
            digest = build_digest([internship], days=7)
        self.assertIn(internship.title, digest)
        self.assertIn(internship.url, digest)
        self.assertIn("Набор открыт", digest)

    def test_pipeline_roundtrip_keeps_manual_internship_in_digest(self):
        source = SimpleNamespace(name="manual_feed", fetch=lambda: [_event()])
        with tempfile.TemporaryDirectory() as temp:
            events_file = Path(temp) / "events.json"
            events, _, _ = collect([source], events_file=events_file)
            save_events(events_file, events)
            stored, _, _ = collect([source], events_file=events_file)
        with patch("src.agents.digest.get_llm_client", return_value=None):
            digest = build_digest(stored, days=7)
        self.assertIn("Стажировки QA / тестирование (rabota.by)", digest)

    def test_open_internship_date_line_is_enrollment_not_catalog_stamp(self):
        self.assertIn("Набор открыт", format_event_date(_event()))

    def test_recent_rabota_vacancy_stays_in_digest_stale_one_does_not(self):
        today = date.today().isoformat()
        stale = (date.today() - timedelta(days=90)).isoformat()
        recent = _event(
            id="rabota-new",
            title="QA Junior",
            url="https://rabota.by/vacancy/1",
            source="rabota_by:qa_junior",
            fetched_at=f"{today}T05:00:00+03:00",
            date=None,
        )
        old = _event(
            id="rabota-old",
            title="Closed QA listing",
            url="https://rabota.by/vacancy/2",
            source="rabota_by:qa_junior",
            fetched_at=f"{stale}T05:00:00+03:00",
            date=None,
        )
        with patch("src.agents.digest.get_llm_client", return_value=None):
            digest = build_digest([recent, old], days=7)
        self.assertIn("QA Junior", digest)
        self.assertNotIn("Closed QA listing", digest)


if __name__ == "__main__":
    unittest.main()
