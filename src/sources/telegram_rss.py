"""Telegram public channel via RSS proxy (RSSHub and mirrors)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import urlparse

import feedparser

from src.models import Event

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_ZW_RE = re.compile(r"[\u200b-\u200d\ufeff]")

_IT_KEYWORDS = (
    "митап",
    "meetup",
    "стажир",
    "intern",
    "конферен",
    "ваканс",
    "junior",
    "qa",
    "python",
    "курс",
    "воркшоп",
    "workshop",
    "вебинар",
    "it",
    "ит",
    "мероприят",
    "событ",
    "jobs",
    "хакатон",
    "hackathon",
)

_DEFAULT_MIRRORS = (
    "https://rsshub.rssforever.com/telegram/channel/{channel}",
    "https://rsshub.app/telegram/channel/{channel}",
)


class TelegramRssSource:
    name = "telegram_rss:belarusitwant"

    def __init__(self, *, channel: str, feed_url: str) -> None:
        self.channel = channel.lstrip("@")
        self.feed_url = feed_url

    def fetch(self) -> list[Event]:
        last_error: Exception | None = None
        urls = [self.feed_url, *_mirror_urls(self.channel, self.feed_url)]

        for url in _unique_urls(urls):
            try:
                events = self._fetch_url(url)
                if events:
                    return events
            except Exception as exc:  # noqa: BLE001 — try next mirror
                last_error = exc

        if last_error:
            raise last_error
        return []

    def _fetch_url(self, url: str) -> list[Event]:
        parsed = feedparser.parse(url)
        if parsed.bozo and not parsed.entries:
            raise RuntimeError(f"RSS parse error: {parsed.bozo_exception}")

        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        events: list[Event] = []

        for entry in parsed.entries:
            event = _entry_to_event(entry, channel=self.channel, fetched_at=now)
            if event is not None:
                events.append(event)

        return events


def _mirror_urls(channel: str, primary: str) -> list[str]:
    mirrors = [template.format(channel=channel) for template in _DEFAULT_MIRRORS]
    return [u for u in mirrors if u != primary]


def _unique_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def _entry_to_event(entry: Any, *, channel: str, fetched_at: str) -> Event | None:
    link = (entry.get("link") or entry.get("id") or "").strip()
    if not link or "t.me/" not in link:
        return None

    raw_title = _clean_text(entry.get("title") or "")
    summary = _clean_text(entry.get("summary") or "")
    body = raw_title or summary
    if not body:
        return None

    if not _looks_relevant(body):
        return None

    post_id = _post_id_from_url(link)
    event_id = f"tg-{channel}-{post_id}" if post_id else f"tg-{channel}-{_hash_slug(link)}"

    return Event(
        id=event_id,
        type=_infer_type(body),
        title=_truncate(raw_title or summary, 200),
        url=link,
        source=f"telegram_rss:{channel}",
        fetched_at=fetched_at,
        date=_entry_date(entry),
        location=_infer_location(body),
        tags=_infer_tags(body, channel),
        source_url=f"https://t.me/{channel}",
    )


def _looks_relevant(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in _IT_KEYWORDS)


def _infer_type(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in ("стажир", "intern", "ваканс", "jobs")):
        return "internship"
    if any(k in lower for k in ("конферен", "conference")):
        return "conference"
    return "meetup"


def _infer_location(text: str) -> str:
    lower = text.lower()
    if "online" in lower or "онлайн" in lower or "remote" in lower:
        return "online"
    if "минск" in lower:
        return "Минск"
    return "Беларусь / online"


def _infer_tags(text: str, channel: str) -> list[str]:
    lower = text.lower()
    tags = ["telegram", channel]
    for tag in ("meetup", "internship", "junior", "qa", "python", "remote", "minsk", "online"):
        if tag in lower or (tag == "internship" and "стажир" in lower):
            tags.append(tag)
    if "митап" in lower or "meetup" in lower:
        tags.append("meetup")
    return list(dict.fromkeys(tags))


def _entry_date(entry: Any) -> str | None:
    published = entry.get("published") or entry.get("updated")
    if not published:
        return None
    try:
        dt = parsedate_to_datetime(published)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _post_id_from_url(url: str) -> str | None:
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if len(parts) >= 2 and parts[-1].isdigit():
        return parts[-1]
    return None


def _hash_slug(url: str) -> str:
    return str(abs(hash(url)))[-10:]


def _clean_text(raw: str) -> str:
    text = unescape(raw)
    text = _TAG_RE.sub(" ", text)
    text = _ZW_RE.sub("", text)
    return _WS_RE.sub(" ", text).strip()


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
