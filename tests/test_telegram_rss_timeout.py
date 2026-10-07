"""RSS fetch must not hang the digest pipeline.

TelegramRssSource is collected before rabota.by / Habr Career. feedparser.parse(url)
uses urllib with no timeout, so a stalled RSSHub mirror (observed: rssforever.com
read timeout, rsshub.app 403) blocked GitHub Actions until timeout-minutes: 10
and the digest was never sent.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.agents.collector import collect
from src.models import Event
from src.sources.telegram_rss import (
    TelegramRssSource,
    _FETCH_TIMEOUT_SEC,
    _download_feed,
)


_SAMPLE_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>belarusitwant</title>
    <item>
      <title>QA стажировка в Минске</title>
      <link>https://t.me/belarusitwant/42</link>
      <pubDate>Wed, 09 Sep 2026 10:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>
"""


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class TelegramRssTimeoutTests(unittest.TestCase):
    def test_download_passes_hard_timeout_to_urlopen(self) -> None:
        calls: list[float | None] = []

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            calls.append(timeout)
            return _FakeResponse(_SAMPLE_RSS.encode())

        with patch("src.sources.telegram_rss.urllib.request.urlopen", fake_urlopen):
            raw = _download_feed("https://rsshub.example/feed")

        self.assertEqual(calls, [_FETCH_TIMEOUT_SEC])
        self.assertIn(b"t.me/belarusitwant/42", raw)

    def test_timeout_on_primary_falls_through_to_mirror(self) -> None:
        source = TelegramRssSource(
            channel="belarusitwant",
            feed_url="https://rsshub.rssforever.com/telegram/channel/belarusitwant",
        )
        attempted: list[str] = []

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            url = request.full_url
            attempted.append(url)
            self.assertEqual(timeout, _FETCH_TIMEOUT_SEC)
            if "rssforever" in url:
                raise TimeoutError("The read operation timed out")
            return _FakeResponse(_SAMPLE_RSS.encode())

        with patch("src.sources.telegram_rss.urllib.request.urlopen", fake_urlopen):
            events = source.fetch()

        self.assertGreaterEqual(len(attempted), 2)
        self.assertIn("rssforever", attempted[0])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].url, "https://t.me/belarusitwant/42")
        self.assertEqual(events[0].title, "QA стажировка в Минске")

    def test_timeout_is_raised_as_runtime_error_not_hang(self) -> None:
        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            raise TimeoutError("The read operation timed out")

        with patch("src.sources.telegram_rss.urllib.request.urlopen", fake_urlopen):
            with self.assertRaises(RuntimeError) as ctx:
                _download_feed("https://rsshub.rssforever.com/telegram/channel/x")

        self.assertIn("timeout", str(ctx.exception).lower())
        self.assertIn(str(_FETCH_TIMEOUT_SEC), str(ctx.exception))

    def test_collect_still_runs_later_sources_when_rss_times_out(self) -> None:
        rss = TelegramRssSource(
            channel="belarusitwant",
            feed_url="https://rsshub.rssforever.com/telegram/channel/belarusitwant",
        )

        class VacancySource:
            name = "rabota_by:qa_junior"

            def fetch(self) -> list[Event]:
                return [
                    Event(
                        id="rabota-by-1",
                        type="internship",
                        title="QA Manual Trainee",
                        url="https://rabota.by/vacancy/1",
                        source=self.name,
                        fetched_at="2026-09-10T08:00:00+03:00",
                    )
                ]

        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            raise TimeoutError("The read operation timed out")

        with patch("src.sources.telegram_rss.urllib.request.urlopen", fake_urlopen):
            events, errors, stats = collect([rss, VacancySource()])

        self.assertIn(rss.name, errors)
        self.assertIn("timeout", errors[rss.name].lower())
        self.assertEqual(stats.added, 1)
        self.assertEqual(events[0].title, "QA Manual Trainee")


if __name__ == "__main__":
    unittest.main()
