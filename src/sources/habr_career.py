"""Habr Career — QA remote intern/junior vacancies (HTML search)."""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from src.models import Event

_USER_AGENT = "PerviyAgent/0.4 (personal monitoring; +local)"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

_QA_TITLE_RE = re.compile(
    r"\b("
    r"qa|"
    r"quality assurance|"
    r"software tester|"
    r"test engineer|"
    r"sdet|"
    r"тестиров|"
    r"manual test|"
    r"automation test"
    r")\b",
    re.IGNORECASE,
)

_JUNIOR_RE = re.compile(
    r"\b(trainee|junior|intern|стажир|стаж[ёe]р|pre-trainee|beginner|начинающ)\b",
    re.IGNORECASE,
)

_SENIOR_RE = re.compile(
    r"\b(lead|senior|middle|principal|staff|head of)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _VacancyCard:
    vacancy_id: str
    title: str
    url: str
    company: str
    published_date: str | None


class HabrCareerQaSource:
    name = "habr_career:qa_remote_junior"

    def __init__(
        self,
        *,
        max_results: int = 30,
        request_delay_sec: float = 1.0,
    ) -> None:
        self.max_results = max_results
        self.request_delay_sec = request_delay_sec

    def fetch(self) -> list[Event]:
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        seen_ids: set[str] = set()
        events: list[Event] = []

        for url, require_junior_hint in self._search_urls():
            html = self._fetch_html(url)
            for card in _parse_cards(html):
                if card.vacancy_id in seen_ids:
                    continue
                if not _matches_qa_junior(card.title, require_junior_hint=require_junior_hint):
                    continue
                seen_ids.add(card.vacancy_id)
                events.append(_to_event(card, fetched_at=now))
                if len(events) >= self.max_results:
                    return events
            time.sleep(self.request_delay_sec)

        return events

    def _search_urls(self) -> list[tuple[str, bool]]:
        base = "https://career.habr.com/vacancies"
        return [
            (f"{base}?q=QA&remote=true&qualification=intern", False),
            (f"{base}?q=QA&remote=true&qualification=junior", False),
            (f"{base}?q=QA+trainee&remote=true", True),
            (f"{base}?q=QA+intern&remote=true", True),
        ]

    def _fetch_html(self, url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"career.habr.com HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"career.habr.com unavailable: {exc.reason}") from exc


def _parse_cards(html: str) -> list[_VacancyCard]:
    cards: dict[str, _VacancyCard] = {}

    for match in re.finditer(
        r'aria-label="([^"]+)"[^>]*href="/vacancies/(\d+)"',
        html,
    ):
        vacancy_id = match.group(2)
        if vacancy_id in cards:
            continue
        chunk = html[match.start() : match.start() + 2000]
        cards[vacancy_id] = _VacancyCard(
            vacancy_id=vacancy_id,
            title=_WS_RE.sub(" ", match.group(1)).strip(),
            url=f"https://career.habr.com/vacancies/{vacancy_id}",
            company=_extract_company(chunk),
            published_date=_extract_published_date(chunk),
        )

    return list(cards.values())


def _extract_company(chunk: str) -> str:
    for pattern in (
        r'vacancy-card__company-title[^>]*>([^<]+)',
        r'class="link-comp[^"]*"[^>]*>([^<]+)',
        r'vacancy-card__meta[^>]*>([^<]+)',
    ):
        match = re.search(pattern, chunk, flags=re.IGNORECASE)
        if match:
            text = _TAG_RE.sub(" ", match.group(1))
            return _WS_RE.sub(" ", text).strip()
    return ""


def _extract_published_date(chunk: str) -> str | None:
    match = re.search(r'datetime="(\d{4}-\d{2}-\d{2})', chunk)
    return match.group(1) if match else None


def _matches_qa_junior(title: str, *, require_junior_hint: bool) -> bool:
    if not _QA_TITLE_RE.search(title):
        return False
    if _SENIOR_RE.search(title) and not _JUNIOR_RE.search(title):
        return False
    if require_junior_hint:
        return bool(_JUNIOR_RE.search(title))
    return True


def _to_event(card: _VacancyCard, *, fetched_at: str) -> Event:
    title_lower = card.title.lower()
    tags = ["habr.career", "internship", "qa", "junior", "remote"]
    if card.company:
        tags.append(card.company)
    if "trainee" in title_lower or "стаж" in title_lower:
        tags.append("trainee")
    if "automation" in title_lower or "sdet" in title_lower:
        tags.append("automation")

    return Event(
        id=f"habr-career-{card.vacancy_id}",
        type="internship",
        title=card.title,
        url=card.url,
        source=HabrCareerQaSource.name,
        fetched_at=fetched_at,
        date=None,
        location="remote",
        tags=list(dict.fromkeys(tags)),
        source_url=card.url,
    )
