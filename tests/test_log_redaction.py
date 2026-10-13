"""Telegram token must never reach log output."""
from __future__ import annotations

import io
import logging
import unittest

from src.bot.run import TokenRedactingFilter, configure_logging

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
