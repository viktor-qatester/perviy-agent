"""Manual JSON feed — MVP source."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from src.models import Event


class ManualFeedSource:
    name = "manual_feed"

    def __init__(self, path: Path) -> None:
        self.path = path

    def fetch(self) -> list[Event]:
        if not self.path.exists():
            return []

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

        events: list[Event] = []
        for item in raw:
            item = dict(item)
            item.setdefault("fetched_at", now)
            item.setdefault("source", self.name)
            events.append(Event.from_dict(item))
        return events
