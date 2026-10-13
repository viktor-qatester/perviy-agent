"""Print upcoming scheduled digest runs without network, polling or sending.

Usage: python scripts/check_schedule.py [--expect-days mon,thu]

Builds the real JobQueue trigger from the current settings (.env / environment),
prints the next 6 fire times and exits non-zero if the schedule is disabled or
does not match the expected weekdays, 05:00 and Europe/Minsk. Secrets are never
read or printed.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram.ext import JobQueue  # noqa: E402

from src.bot.schedule import parse_schedule_days, setup_schedule  # noqa: E402
from src.config import settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-days", default="mon,thu")
    parser.add_argument("--expect-time", default="05:00")
    parser.add_argument("--expect-timezone", default="Europe/Minsk")
    args = parser.parse_args()

    print(
        f"SCHEDULE_ENABLED={settings.schedule_enabled} SCHEDULE_DAYS={settings.schedule_days} "
        f"SCHEDULE_TIME={settings.schedule_time} TIMEZONE={settings.timezone}"
    )
    queue = JobQueue()
    setup_schedule(SimpleNamespace(job_queue=queue), settings)
    jobs = queue.scheduler.get_jobs()
    if len(jobs) != 1:
        print(f"FAIL: expected exactly 1 scheduled job, found {len(jobs)}")
        return 1

    tz = ZoneInfo(settings.timezone)
    now, previous, fires = datetime.now(tz), None, []
    for _ in range(6):
        previous = jobs[0].trigger.get_next_fire_time(previous, now)
        fires.append(previous)
        print(previous.strftime("%a %Y-%m-%d %H:%M %z"))
        now = previous + timedelta(seconds=1)

    expected_days = {(d - 1) % 7 for d in parse_schedule_days(args.expect_days)}  # PTB Sunday=0 -> weekday() Monday=0
    hh, mm = (int(part) for part in args.expect_time.split(":"))
    problems = []
    if settings.timezone != args.expect_timezone:
        problems.append(f"timezone {settings.timezone} != {args.expect_timezone}")
    for fire in fires:
        if fire.weekday() not in expected_days or (fire.hour, fire.minute) != (hh, mm):
            problems.append(f"unexpected fire time {fire.isoformat()}")
    if problems:
        print("FAIL: " + "; ".join(problems))
        return 1
    print(f"OK: only {args.expect_days} at {args.expect_time} {args.expect_timezone}; nothing was sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
