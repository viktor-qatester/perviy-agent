"""One failed vacancy search URL must not drop cards already parsed."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from src.sources.habr_career import HabrCareerQaSource
from src.sources.rabota_by import RabotaByQaSource

RABOTA_CARD_HTML = (
    'prefix class="vacancy-card--info">'
    '<a href="/vacancy/11111" class="vacancy-name-wrapper">QA Trainee</a>'
)

HABR_CARD_HTML = 'aria-label="QA Intern" href="/vacancies/22222"'


class RabotaByFetchResilienceTests(unittest.TestCase):
    def setUp(self):
        self.source = RabotaByQaSource(request_delay_sec=0)
        self.urls = [
            ("https://rabota.by/stazhirovki?q=QA", True),
            ("https://rabota.by/search/vacancy?text=QA", False),
        ]

    def test_later_url_failure_keeps_cards_from_earlier_page(self):
        with (
            patch.object(self.source, "_search_urls", return_value=self.urls),
            patch.object(
                self.source,
                "_fetch_html",
                side_effect=[RABOTA_CARD_HTML, RuntimeError("HTTP 403")],
            ),
        ):
            events = self.source.fetch()

        self.assertEqual([event.id for event in events], ["rabota-by-11111"])
        self.assertEqual(events[0].title, "QA Trainee")

    def test_first_url_failure_still_uses_later_page(self):
        with (
            patch.object(self.source, "_search_urls", return_value=self.urls),
            patch.object(
                self.source,
                "_fetch_html",
                side_effect=[RuntimeError("HTTP 503"), RABOTA_CARD_HTML],
            ),
        ):
            events = self.source.fetch()

        self.assertEqual([event.id for event in events], ["rabota-by-11111"])

    def test_all_urls_failing_still_raises(self):
        with (
            patch.object(self.source, "_search_urls", return_value=self.urls),
            patch.object(self.source, "_fetch_html", side_effect=RuntimeError("down")),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                self.source.fetch()
        self.assertEqual(str(ctx.exception), "down")


class HabrCareerFetchResilienceTests(unittest.TestCase):
    def setUp(self):
        self.source = HabrCareerQaSource(request_delay_sec=0)
        self.urls = [
            ("https://career.habr.com/vacancies?q=QA&qualification=intern", False),
            ("https://career.habr.com/vacancies?q=QA&qualification=junior", False),
        ]

    def test_later_url_failure_keeps_cards_from_earlier_page(self):
        with (
            patch.object(self.source, "_search_urls", return_value=self.urls),
            patch.object(
                self.source,
                "_fetch_html",
                side_effect=[HABR_CARD_HTML, RuntimeError("HTTP 403")],
            ),
        ):
            events = self.source.fetch()

        self.assertEqual([event.id for event in events], ["habr-career-22222"])
        self.assertEqual(events[0].title, "QA Intern")

    def test_first_url_failure_still_uses_later_page(self):
        with (
            patch.object(self.source, "_search_urls", return_value=self.urls),
            patch.object(
                self.source,
                "_fetch_html",
                side_effect=[RuntimeError("HTTP 503"), HABR_CARD_HTML],
            ),
        ):
            events = self.source.fetch()

        self.assertEqual([event.id for event in events], ["habr-career-22222"])

    def test_all_urls_failing_still_raises(self):
        with (
            patch.object(self.source, "_search_urls", return_value=self.urls),
            patch.object(self.source, "_fetch_html", side_effect=RuntimeError("down")),
        ):
            with self.assertRaises(RuntimeError):
                self.source.fetch()


if __name__ == "__main__":
    unittest.main()
