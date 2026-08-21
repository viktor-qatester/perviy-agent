"""rabota.by — QA Trainee/Junior vacancies (HTML search, no API key)."""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from src.models import Event

_USER_AGENT = "PerviyAgent/0.3 (personal monitoring; +local)"
_CARD_SPLIT = 'class="vacancy-card--'
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

_QA_TITLE_RE = re.compile(
    r"\b("
    r"qa|"
    r"quality assurance|"
    r"software tester|"
    r"test engineer|"
    r"тестиров|"
    r"manual test|"
    r"automation test"
    r")\b",
    re.IGNORECASE,
)

_JUNIOR_RE = re.compile(
    r"\b(trainee|junior|intern|стажир|pre-trainee|beginner|начинающ)\b|без опыта",
    re.IGNORECASE,
)

_STAZHIROVKI_HINT = re.compile(r"стажир|trainee|intern|практик", re.IGNORECASE)


@dataclass(frozen=True)
class _VacancyCard:
    vacancy_id: str
    title: str
    url: str
    location: str
    is_internship_page: bool


class RabotaByQaSource:
    name = "rabota_by:qa_junior"

    def __init__(
        self,
        *,
        area: str = "1002",
        max_results: int = 30,
        request_delay_sec: float = 1.0,
    ) -> None:
        self.area = area
        self.max_results = max_results
        self.request_delay_sec = request_delay_sec

    def fetch(self) -> list[Event]:
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        seen_ids: set[str] = set()
        events: list[Event] = []

        for url, is_internship_page in self._search_urls():
            html = self._fetch_html(url)
            for card in self._parse_cards(html, is_internship_page=is_internship_page):
                if card.vacancy_id in seen_ids:
                    continue
                if not _matches_qa_junior(card):
                    continue
                seen_ids.add(card.vacancy_id)
                events.append(_to_event(card, fetched_at=now))
                if len(events) >= self.max_results:
                    return events
            time.sleep(self.request_delay_sec)

        return events

    def _search_urls(self) -> list[tuple[str, bool]]:
        area = self.area
        return [
            (
                f"https://rabota.by/stazhirovki?q=QA&area={area}",
                True,
            ),
            (
                "https://rabota.by/search/vacancy?"
                f"text=QA&experience=noExperience&area={area}&order_by=publication_time",
                False,
            ),
            (
                "https://rabota.by/search/vacancy?"
                f"text=QA+trainee&experience=noExperience&area={area}&order_by=publication_time",
                False,
            ),
            (
                "https://rabota.by/search/vacancy?"
                f"text=QA+junior&experience=noExperience&area={area}&order_by=publication_time",
                False,
            ),
        ]

    def _fetch_html(self, url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:300]
            raise RuntimeError(f"rabota.by HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"rabota.by unavailable: {exc.reason}") from exc

    def _parse_cards(self, html: str, *, is_internship_page: bool) -> list[_VacancyCard]:
        cards: list[_VacancyCard] = []
        for part in html.split(_CARD_SPLIT)[1:]:
            vacancy_id_match = re.search(r"/vacancy/(\d+)", part)
            if not vacancy_id_match:
                continue

            title = _extract_title(part)
            if not title:
                continue

            vacancy_id = vacancy_id_match.group(1)
            cards.append(
                _VacancyCard(
                    vacancy_id=vacancy_id,
                    title=title,
                    url=f"https://rabota.by/vacancy/{vacancy_id}",
                    location=_extract_location(part),
                    is_internship_page=is_internship_page,
                )
            )
        return cards


def _extract_title(part: str) -> str:
    title_match = re.search(r"vacancy-name-wrapper.*?>(.*?)</a>", part, flags=re.DOTALL)
    if not title_match:
        return ""
    text = _TAG_RE.sub(" ", title_match.group(1))
    return _WS_RE.sub(" ", text).strip()


def _extract_location(part: str) -> str:
    if "online" in part.lower() or "удал" in part.lower():
        return "online"
    if "Минск" in part:
        return "Минск"
    return "Беларусь"


def _matches_qa_junior(card: _VacancyCard) -> bool:
    title = card.title
    if not _QA_TITLE_RE.search(title):
        return False
    if card.is_internship_page:
        return True
    if _JUNIOR_RE.search(title):
        return True
    return bool(_STAZHIROVKI_HINT.search(title))


def _to_event(card: _VacancyCard, *, fetched_at: str) -> Event:
    title_lower = card.title.lower()
    tags = ["rabota.by", "internship", "qa", "junior", "minsk"]
    if "trainee" in title_lower or "стаж" in title_lower:
        tags.append("trainee")
    if "remote" in title_lower or card.location == "online":
        tags.append("remote")

    return Event(
        id=f"rabota-by-{card.vacancy_id}",
        type="internship",
        title=card.title,
        url=card.url,
        source=RabotaByQaSource.name,
        fetched_at=fetched_at,
        date=None,
        location=card.location,
        tags=list(dict.fromkeys(tags)),
        source_url=card.url,
    )
