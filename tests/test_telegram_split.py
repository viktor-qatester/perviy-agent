"""Telegram splits must stay within the Bot API UTF-16 length limit."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from datetime import datetime, timezone

from src.agents.digest import _template_digest
from src.bot import handlers
from src.bot.state import BotState
from src.models import Event
from src.notifiers.telegram import (
    HITL_CALLBACK_APPROVE,
    _split_text,
    _telegram_len,
)


TELEGRAM_MAX = 4096

_INTERNSHIP_TITLES = [
    "Software QA Engineer/Intern (AI-Powered)",
    "QA Manual Trainee",
    "QA Automation Trainee",
    "Junior QA Engineer",
    "Full Stack Test Engineer Trainee",
    "QA инженер",
    "QA Automation Engineer (Python)",
    "QA инженер (Linux)",
    "QA Automation Engineer / SDET",
    "QA Engineer — Web, Backend, API, Linux",
    "QA тестировщик со знанием платформы ЦФТ/ Проектная работа / АУТСТАФФ",
    "QA engineer",
    "QA-инженер/тестировщик",
    "Automation QA (Java)",
    "QA Fullstack (C#)",
    "SDET / QA Automation (Java)",
    "FullStack QA (Java)",
    "Функциональный тестировщик / QA инженер",
    "QA инженер (java/kotlin)",
    "Функциональный тестировщик / QA инженер (стажировка)",
    "Fullstack QA (IaaS Terraform)",
    "Инженер по тестированию (Python / API) / QA Engineer",
    "Инженер по автоматизации тестирования (Java) / QA Automation Engineer",
    "Инженер по нагрузочному тестированию (JMeter) / Performance QA Engineer",
]


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _internship_digest() -> str:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    events = []
    for index, title in enumerate(_INTERNSHIP_TITLES):
        events.append(
            Event(
                id=f"vacancy-{index}",
                type="internship",
                title=title,
                url=f"https://career.habr.com/vacancies/{1_000_000_000 + index}",
                source="habr_career:qa_remote_junior",
                fetched_at=now,
                date=None,
                location="remote",
                tags=["habr.career", "internship", "qa", "junior", "remote"],
            )
        )
    return _template_digest(events, 7)


class SplitTextTests(unittest.TestCase):
    def test_ascii_split_unchanged(self):
        chunks = _split_text("a" * 4000 + "\n" + "b" * 1000, limit=TELEGRAM_MAX)
        self.assertEqual([c[0] for c in chunks], ["a", "b"])
        self.assertEqual(len(chunks[0]), 4000)
        self.assertEqual(len(chunks[1]), 1000)

    def test_non_bmp_emoji_does_not_exceed_utf16_limit(self):
        # 4095 BMP chars + one 🟢 is 4097 UTF-16 units — must not be one chunk.
        text = "a" * 4095 + "🟢" + "tail"
        chunks = _split_text(text, limit=TELEGRAM_MAX)
        self.assertGreaterEqual(len(chunks), 2)
        for chunk in chunks:
            self.assertLessEqual(_utf16_len(chunk), TELEGRAM_MAX)
        self.assertEqual("".join(chunks).replace("\n", ""), text)

    def test_internship_digest_with_open_badges_fits_telegram(self):
        digest = _internship_digest()

        self.assertGreater(_utf16_len(digest), TELEGRAM_MAX)

        chunks = _split_text(digest, limit=TELEGRAM_MAX)
        joined = "\n".join(chunks)
        self.assertGreaterEqual(len(chunks), 2)
        for chunk in chunks:
            self.assertLessEqual(_utf16_len(chunk), TELEGRAM_MAX)
            self.assertLessEqual(_telegram_len(chunk), TELEGRAM_MAX)
        self.assertEqual(joined.count("🟢"), digest.count("🟢"))
        for title in _INTERNSHIP_TITLES:
            self.assertIn(title, joined)


class HitlUtf16PublishTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.settings = SimpleNamespace(
            bot_state_file=root / "state.json",
            logs_dir=root / "logs",
            authorized_chat_id=lambda: "123",
            publish_channel_id=lambda: "-100456",
        )
        self.bot = SimpleNamespace(send_message=AsyncMock())
        self.context = SimpleNamespace(bot_data={"settings": self.settings}, bot=self.bot)

    async def test_approve_sends_only_utf16_safe_chunks(self):
        digest = _internship_digest()

        state = BotState()
        state.set_pending(digest)
        state.save(self.settings.bot_state_file)

        query = SimpleNamespace(
            data=f"{HITL_CALLBACK_APPROVE}:{state.draft_id}",
            answer=AsyncMock(),
            edit_message_reply_markup=AsyncMock(),
            message=SimpleNamespace(reply_text=AsyncMock()),
        )
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=123),
            callback_query=query,
        )

        await handlers.on_callback(update, self.context)

        self.assertFalse(BotState.load(self.settings.bot_state_file).pending_digest)
        sent = [call.kwargs["text"] for call in self.bot.send_message.await_args_list]
        self.assertGreaterEqual(len(sent), 2)
        for chunk in sent:
            self.assertLessEqual(_utf16_len(chunk), TELEGRAM_MAX)
        query.edit_message_reply_markup.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
