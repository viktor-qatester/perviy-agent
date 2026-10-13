"""Check actual JobQueue fire dates, not just our weekday constants."""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from telegram.ext import JobQueue

from src.bot.schedule import parse_schedule_days, setup_schedule


class ScheduleRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_jobqueue_fires_only_monday_thursday_at_five_minsk(self):
        queue = JobQueue()
        app = SimpleNamespace(job_queue=queue)
        settings = SimpleNamespace(
            schedule_enabled=True,
            schedule_days="mon,thu",
            schedule_time="05:00",
            timezone="Europe/Minsk",
        )
        setup_schedule(app, settings)
        job, = queue.scheduler.get_jobs()
        tz = ZoneInfo("Europe/Minsk")
        now = datetime(2026, 10, 5, 0, 0, tzinfo=tz)  # Monday
        previous = None
        actual = []
        for _ in range(6):
            previous = job.trigger.get_next_fire_time(previous, now)
            actual.append(previous)
            now = previous + timedelta(seconds=1)
        expected = [datetime(2026, 10, day, 5, 0, tzinfo=tz)
                    for day in (5, 8, 12, 15, 19, 22)]
        self.assertEqual(actual, expected)
        self.assertTrue(all(d.weekday() in (0, 3) for d in actual))
        self.assertTrue(all(d.utcoffset() == timedelta(hours=3) for d in actual))

    async def test_disabled_local_schedule_creates_no_job(self):
        queue = JobQueue()
        setup_schedule(SimpleNamespace(job_queue=queue),
                       SimpleNamespace(schedule_enabled=False))
        self.assertEqual(queue.scheduler.get_jobs(), [])

    async def test_aliases_and_invalid_days(self):
        for index, day in enumerate(("sunday", "monday", "tuesday", "wednesday",
                                     "thursday", "friday", "saturday")):
            with self.subTest(day=day):
                self.assertEqual(parse_schedule_days(day), (index,))
        self.assertEqual(parse_schedule_days(" FRI, tue,friday "), (2, 5))
        for raw in ("", "holiday"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_schedule_days(raw)


if __name__ == "__main__":
    unittest.main()
