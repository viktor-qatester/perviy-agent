"""Trailing whitespace in TELEGRAM_BOT_TOKEN must not break digest delivery.

GitHub Actions run 33785390050 failed with:
  URL can't contain control characters. '/bot***\\n\\n/sendMessage'
because the secret was pasted with trailing newlines. Chat IDs were already
stripped; the bot token was not.
"""

from __future__ import annotations

import http.client
import json
import unittest
import urllib.request
from unittest.mock import patch

from src.config import Settings
from src.notifiers.telegram import send_telegram_hitl_draft, send_telegram_message


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class TelegramTokenStripTests(unittest.TestCase):
    def test_settings_strips_newlines_from_bot_token(self) -> None:
        settings = Settings(telegram_bot_token="123:AAAxxx\n\n")
        self.assertEqual(settings.telegram_bot_token, "123:AAAxxx")
        self.assertEqual(
            Settings(telegram_bot_token="  123:AAAxxx  ").telegram_bot_token,
            "123:AAAxxx",
        )
        self.assertEqual(Settings(telegram_bot_token="\n\n").telegram_bot_token, "")

    def test_newline_in_token_makes_raw_api_url_illegal(self) -> None:
        dirty = "123:AAAxxx\n\n"
        dirty_url = f"https://api.telegram.org/bot{dirty}/sendMessage"
        request = urllib.request.Request(dirty_url, data=b"{}", method="POST")
        with self.assertRaises(http.client.InvalidURL) as ctx:
            urllib.request.urlopen(request, timeout=1)
        self.assertIn("control characters", str(ctx.exception).lower())

        clean_url = f"https://api.telegram.org/bot{dirty.strip()}/sendMessage"
        urllib.request.Request(clean_url, data=b"{}", method="POST")

    def test_whitespace_only_token_is_treated_as_missing(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            send_telegram_message(token="\n\n", chat_id="1", text="hi")
        self.assertIn("TELEGRAM_BOT_TOKEN", str(ctx.exception))

        with self.assertRaises(ValueError):
            send_telegram_hitl_draft(
                token="\n",
                chat_id="1",
                title="IT-события BY — 07.09.2026",
                digest="draft",
            )

    def test_send_strips_token_before_building_api_url(self) -> None:
        captured: list[str] = []

        def fake_urlopen(request: urllib.request.Request, timeout: int = 0):
            captured.append(request.full_url)
            return _FakeResponse({"ok": True, "result": {}})

        with patch("src.notifiers.telegram.urllib.request.urlopen", fake_urlopen):
            send_telegram_message(
                token="123:AAAxxx\n\n",
                chat_id="  42\n",
                text="hi",
            )

        self.assertEqual(captured, ["https://api.telegram.org/bot123:AAAxxx/sendMessage"])
        urllib.request.Request(captured[0], data=b"{}", method="POST")


if __name__ == "__main__":
    unittest.main()
