"""Regression tests for HITL draft identity and resumable publication."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.bot import handlers
from src.bot.state import BotState
from src.notifiers.telegram import HITL_CALLBACK_APPROVE, HITL_CALLBACK_CANCEL


class HitlTests(unittest.IsolatedAsyncioTestCase):
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

    def callback(self, data):
        query = SimpleNamespace(
            data=data,
            answer=AsyncMock(),
            edit_message_reply_markup=AsyncMock(),
            message=SimpleNamespace(reply_text=AsyncMock()),
        )
        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=123),
            callback_query=query,
        )
        return update, query

    async def test_old_button_cannot_cancel_new_draft(self):
        state = BotState()
        state.set_pending("old")
        old_id = state.draft_id
        state.set_pending("new")
        state.save(self.settings.bot_state_file)

        update, query = self.callback(f"{HITL_CALLBACK_CANCEL}:{old_id}")
        await handlers.on_callback(update, self.context)

        self.assertEqual(BotState.load(self.settings.bot_state_file).pending_digest, "new")
        query.answer.assert_awaited_once()
        self.assertTrue(query.answer.await_args.kwargs["show_alert"])
        query.edit_message_reply_markup.assert_not_awaited()

    async def test_partial_failure_keeps_draft_and_resumes_without_first_chunk(self):
        state = BotState()
        state.set_pending("a" * 4000 + "\n" + "b" * 1000)
        state.save(self.settings.bot_state_file)
        callback_data = f"{HITL_CALLBACK_APPROVE}:{state.draft_id}"
        self.bot.send_message.side_effect = [None, RuntimeError("network"), None]

        update, query = self.callback(callback_data)
        await handlers.on_callback(update, self.context)
        saved = BotState.load(self.settings.bot_state_file)
        self.assertEqual(saved.draft_id, state.draft_id)
        self.assertEqual(saved.published_chunks, 1)
        self.assertEqual(self.bot.send_message.await_count, 2)
        query.edit_message_reply_markup.assert_not_awaited()

        await handlers.on_callback(update, self.context)
        saved = BotState.load(self.settings.bot_state_file)
        self.assertFalse(saved.pending_digest)
        self.assertEqual(self.bot.send_message.await_count, 3)
        self.assertEqual(
            [call.kwargs["text"][0] for call in self.bot.send_message.await_args_list],
            ["a", "b", "b"],
        )
        query.edit_message_reply_markup.assert_awaited_once()

        await handlers.on_callback(update, self.context)
        self.assertEqual(self.bot.send_message.await_count, 3)

    async def test_partial_publish_cannot_be_cancelled(self):
        state = BotState()
        state.set_pending("digest")
        state.published_chunks = 1
        state.save(self.settings.bot_state_file)
        update, _ = self.callback(f"{HITL_CALLBACK_CANCEL}:{state.draft_id}")
        await handlers.on_callback(update, self.context)
        self.assertEqual(BotState.load(self.settings.bot_state_file).pending_digest, "digest")

    async def test_draft_buttons_include_current_id(self):
        state = BotState()
        state.set_pending("digest")
        keyboard = handlers._hitl_keyboard(state.draft_id)
        self.assertEqual(
            keyboard.inline_keyboard[0][0].callback_data,
            f"{HITL_CALLBACK_APPROVE}:{state.draft_id}",
        )


if __name__ == "__main__":
    unittest.main()
