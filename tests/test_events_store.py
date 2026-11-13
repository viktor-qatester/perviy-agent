"""events.json must survive interrupted writes and still load."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.agents.collector import collect, load_events, save_events
from src.models import Event


def _event(event_id: str = "rabota-by-1") -> Event:
    return Event(
        id=event_id,
        type="internship",
        title="QA Intern",
        url=f"https://rabota.by/vacancy/{event_id}",
        source="rabota_by:qa_junior",
        fetched_at="2026-11-13T12:00:00+03:00",
        date=None,
        location="Минск",
        tags=["qa"],
        source_url=f"https://rabota.by/vacancy/{event_id}",
    )


class EventsStoreTests(unittest.TestCase):
    def test_empty_events_file_does_not_crash_load_or_collect(self) -> None:
        """Interrupted Path.write_text leaves an empty file; collect used to JSONDecodeError."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.json"
            path.write_text("", encoding="utf-8")
            self.assertEqual(load_events(path), [])
            events, errors, stats = collect([], events_file=path)
            self.assertEqual(events, [])
            self.assertEqual(errors, {})
            self.assertEqual(stats.kept_existing, 0)

    def test_truncated_json_does_not_crash_load(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.json"
            path.write_text('[{"id": "broken"', encoding="utf-8")
            self.assertEqual(load_events(path), [])

    def test_failed_save_does_not_clobber_existing_events(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.json"
            save_events(path, [_event("keep-me")])
            original = path.read_text(encoding="utf-8")

            with patch("src.agents.collector.os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    save_events(path, [_event("new")])

            self.assertEqual(path.read_text(encoding="utf-8"), original)
            loaded = load_events(path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].id, "keep-me")
            leftovers = list(Path(tmp).glob("events.json*.tmp"))
            self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
