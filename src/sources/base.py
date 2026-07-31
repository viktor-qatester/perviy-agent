"""Source protocol."""

from __future__ import annotations

from typing import Protocol

from src.models import Event


class Source(Protocol):
    name: str

    def fetch(self) -> list[Event]:
        """Return raw events from this source."""
        ...
