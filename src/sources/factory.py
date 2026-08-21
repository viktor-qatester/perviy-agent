"""Build source list from settings."""

from __future__ import annotations

from src.config import Settings
from src.sources.base import Source
from src.sources.habr_career import HabrCareerQaSource
from src.sources.manual_feed import ManualFeedSource
from src.sources.rabota_by import RabotaByQaSource
from src.sources.telegram_rss import TelegramRssSource


def build_sources(settings: Settings) -> list[Source]:
    sources: list[Source] = [ManualFeedSource(settings.manual_feed)]

    if settings.telegram_rss_enabled and settings.telegram_rss_belarusitwant_url:
        sources.append(
            TelegramRssSource(
                channel="belarusitwant",
                feed_url=settings.telegram_rss_belarusitwant_url,
            )
        )

    if settings.rabota_by_enabled:
        sources.append(
            RabotaByQaSource(
                area=settings.rabota_by_area,
                max_results=settings.rabota_by_max_results,
            )
        )

    if settings.habr_career_enabled:
        sources.append(
            HabrCareerQaSource(
                max_results=settings.habr_career_max_results,
            )
        )

    return sources
