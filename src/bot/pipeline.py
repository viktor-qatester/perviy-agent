"""Shared collect + digest helpers for bot and CLI."""

from __future__ import annotations

from src.agents.collector import CollectStats, collect, save_events
from src.agents.digest import build_digest
from src.config import Settings
from src.sources.factory import build_sources


def run_collect_and_digest(
    settings: Settings,
) -> tuple[str, int, dict[str, str], CollectStats]:
    sources = build_sources(settings)
    events, errors, stats = collect(sources, events_file=settings.events_file)
    save_events(settings.events_file, events)
    digest = build_digest(events, days=settings.digest_days_ahead)
    return digest, len(events), errors, stats
