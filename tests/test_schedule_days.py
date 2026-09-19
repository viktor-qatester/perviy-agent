"""SCHEDULE_DAYS must use PTB JobQueue numbering (Sunday=0), not datetime.weekday()."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from datetime import date
from zoneinfo import ZoneInfo

from src.bot.schedule import parse_schedule_days, parse_schedule_time, setup_schedule
from src.config import Settings


class ParseScheduleDaysTests(unittest.TestCase):
    def test_default_tue_fri_is_ptb_tuesday_friday_not_python_weekday(self) -> None:
        days = parse_schedule_days("tue,fri")
        self.assertEqual(days, (2, 5))
        # datetime.weekday(): Tuesday=1, Friday=4 — that mapping is wrong for PTB.
        self.assertNotEqual(days, (date(2026, 8, 25).weekday(), date(2026, 8, 28).weekday()))

    def test_sunday_is_zero_monday_is_one(self) -> None:
        self.assertEqual(parse_schedule_days("sun"), (0,))
        self.assertEqual(parse_schedule_days("sunday"), (0,))
        self.assertEqual(parse_schedule_days("mon"), (1,))
        self.assertEqual(parse_schedule_days("monday"), (1,))

    def test_saturday_is_six(self) -> None:
        self.assertEqual(parse_schedule_days("sat"), (6,))
        self.assertEqual(parse_schedule_days("saturday"), (6,))

    def test_full_names_and_dedup_sorted(self) -> None:
        self.assertEqual(parse_schedule_days("Friday, Tuesday, tue"), (2, 5))

    def test_unknown_day_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_schedule_days("tue,firday")

    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_schedule_days("  ,  ")


class SetupScheduleDaysTests(unittest.TestCase):
    def test_run_daily_receives_sunday_based_days(self) -> None:
        settings = Settings(
            schedule_enabled=True,
            schedule_days="tue,fri",
            schedule_time="05:00",
            timezone="Europe/Moscow",
        )
        app = MagicMock()
        setup_schedule(app, settings)

        app.job_queue.run_daily.assert_called_once()
        kwargs = app.job_queue.run_daily.call_args.kwargs
        self.assertEqual(kwargs["days"], (2, 5))
        self.assertEqual(kwargs["time"], parse_schedule_time("05:00").replace(tzinfo=ZoneInfo("Europe/Moscow")))
        self.assertEqual(kwargs["name"], "scheduled_digest")


if __name__ == "__main__":
    unittest.main()
