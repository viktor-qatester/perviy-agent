"""HITL approve must recover a CI draft from the clicked Telegram message."""

from __future__ import annotations

import unittest
from datetime import datetime

from src.notifiers.telegram import _split_text, recover_digest_from_hitl_message_text


def _cli_hitl_message(digest: str, *, date_str: str = "04.09.2026") -> str:
    return f"IT-события BY — {date_str}\n\n{digest}"


class RecoverDigestFromHitlMessageTests(unittest.TestCase):
    def test_cli_send_message_strips_subject(self) -> None:
        digest = (
            "Дайджест IT-событий (Беларусь) на 7 дней:\n\n"
            "• [internship] QA Intern — 🟢 Набор открыт\n"
            "  https://rabota.by/vacancy/123\n\n"
            "Черновик — требует подтверждения."
        )
        recovered = recover_digest_from_hitl_message_text(_cli_hitl_message(digest))
        self.assertEqual(recovered, digest)

    def test_matches_live_dispatch_subject_format(self) -> None:
        digest = "На ближайшие 7 дней новых событий не найдено.\n\nЧерновик — требует подтверждения."
        title = f"IT-события BY — {datetime.now().strftime('%d.%m.%Y')}"
        recovered = recover_digest_from_hitl_message_text(f"{title}\n\n{digest}")
        self.assertEqual(recovered, digest)

    def test_bot_digest_header_stripped(self) -> None:
        digest = "• Meetup — 2026-09-10\n  https://example.com/event"
        text = "Черновик дайджеста (3 событий, +1 новых)\n\n" + digest
        self.assertEqual(recover_digest_from_hitl_message_text(text), digest)

    def test_scheduled_bot_header_with_source_errors(self) -> None:
        digest = "• QA Intern — 🟢 Набор открыт\n  https://career.habr.com/vacancies/1"
        text = (
            "📅 Автоматический черновик дайджеста (2 событий, +2 новых)\n"
            "⚠ Ошибки источников: {'habr_career:qa_remote_junior': 'timeout'}\n\n"
            + digest
        )
        self.assertEqual(recover_digest_from_hitl_message_text(text), digest)

    def test_split_continuation_chunk_is_not_published(self) -> None:
        digest = "строка дайджеста\n" * 400
        body = _cli_hitl_message(digest)
        chunks = _split_text(body, limit=4000)
        self.assertGreater(len(chunks), 1)
        self.assertIsNotNone(recover_digest_from_hitl_message_text(chunks[0]))
        self.assertIsNone(recover_digest_from_hitl_message_text(chunks[-1]))

    def test_edit_confirmation_stub_is_not_a_digest(self) -> None:
        self.assertIsNone(
            recover_digest_from_hitl_message_text(
                "Черновик обновлён. Проверьте и выберите действие:"
            )
        )

    def test_empty_and_unknown_messages(self) -> None:
        self.assertIsNone(recover_digest_from_hitl_message_text(None))
        self.assertIsNone(recover_digest_from_hitl_message_text(""))
        self.assertIsNone(recover_digest_from_hitl_message_text("   "))
        self.assertIsNone(recover_digest_from_hitl_message_text("IT-события BY — 04.09.2026\n\n"))
        self.assertIsNone(recover_digest_from_hitl_message_text("random callback text"))

    def test_hitl_sender_wrapper_format(self) -> None:
        digest = "hello"
        title = "IT-события BY — 04.09.2026"
        self.assertEqual(
            recover_digest_from_hitl_message_text(f"{title}\n\n{digest}"),
            digest,
        )


if __name__ == "__main__":
    unittest.main()
