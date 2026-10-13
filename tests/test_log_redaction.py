"""Telegram token must never reach log output."""
from __future__ import annotations

import io
import logging
import os
import subprocess
import sys
import unittest
from pathlib import Path

from src.bot.run import TokenRedactingFilter, _known_secrets, configure_logging, register_secret

ROOT = Path(__file__).resolve().parents[1]
FAKE_TOKEN = "1234567890:AAFakeTokenForTests_only-0123456789"


class TokenRedactionTests(unittest.TestCase):
    def setUp(self):
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.addFilter(TokenRedactingFilter())
        self.logger = logging.getLogger("test.redaction")
        self.logger.addHandler(self.handler)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

    def tearDown(self):
        self.logger.removeHandler(self.handler)

    def test_url_in_args_is_redacted(self):
        self.logger.info('HTTP Request: POST %s "HTTP/1.1 200 OK"',
                         f"https://api.telegram.org/bot{FAKE_TOKEN}/getUpdates")
        output = self.stream.getvalue()
        self.assertNotIn(FAKE_TOKEN, output)
        self.assertIn("https://api.telegram.org/bot<redacted>/getUpdates", output)

    def test_exception_traceback_is_redacted(self):
        try:
            raise RuntimeError(f"failed https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage")
        except RuntimeError:
            self.logger.exception("Scheduled digest failed")
        output = self.stream.getvalue()
        self.assertNotIn(FAKE_TOKEN, output)
        self.assertIn("<redacted>", output)

    def test_other_error_formats_are_redacted(self):
        encoded = FAKE_TOKEN.replace(":", "%3A")
        try:
            try:
                raise ConnectionError(f"pool url: /bot{FAKE_TOKEN}/getUpdates")
            except ConnectionError as inner:
                raise RuntimeError("wrapped") from inner
        except RuntimeError:
            self.logger.exception("chained failure")
        self.logger.error("InvalidToken: The token `%s` was rejected by the server.", FAKE_TOKEN)
        self.logger.info("payload %r", {"url": f"https://x/bot{FAKE_TOKEN}/a"})
        self.logger.info("bytes %r", f"bot{FAKE_TOKEN}".encode())
        self.logger.info("encoded bot%s/getMe", encoded)
        self.logger.info("%(url)s", {"url": f"bot{FAKE_TOKEN}"})
        self.logger.info("multi\nline bot%s\nend", FAKE_TOKEN)
        self.logger.error("with stack", stack_info=True)
        output = self.stream.getvalue()
        for leaked in (FAKE_TOKEN, encoded, FAKE_TOKEN.split(":")[1]):
            self.assertNotIn(leaked, output)

    def test_registered_secret_is_redacted_even_if_format_is_unusual(self):
        odd = "not-telegram-shaped-secret"
        register_secret(odd)
        self.addCleanup(_known_secrets.discard, odd)
        self.logger.info("value=%s", odd)
        self.assertNotIn(odd, self.stream.getvalue())

    def test_startup_crash_does_not_print_token_to_stderr(self):
        """A rejected token raises InvalidToken(...token...) before polling starts;
        the default traceback would bypass logging and leak it."""
        code = (
            "from unittest.mock import patch\n"
            "from telegram.error import InvalidToken\n"
            "from types import SimpleNamespace\n"
            "from src.bot import run\n"
            f"token = {FAKE_TOKEN!r}\n"
            "def boom(settings):\n"
            "    raise InvalidToken(f'The token `{token}` was rejected by the server.')\n"
            "with patch.object(run, 'build_application', boom):\n"
            "    run.run_bot(SimpleNamespace(telegram_bot_token=token))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, capture_output=True,
            text=True, encoding="utf-8", timeout=60,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1, combined)
        self.assertNotIn(FAKE_TOKEN, combined)
        self.assertNotIn(FAKE_TOKEN.split(":")[1], combined)
        self.assertIn("<redacted>", combined)

    def test_configure_logging_silences_httpx_info(self):
        configure_logging()
        self.assertGreaterEqual(logging.getLogger("httpx").level, logging.WARNING)
        self.assertGreaterEqual(logging.getLogger("httpcore").level, logging.WARNING)
        self.assertTrue(all(
            any(isinstance(f, TokenRedactingFilter) for f in h.filters)
            for h in logging.getLogger().handlers
        ))


if __name__ == "__main__":
    unittest.main()
