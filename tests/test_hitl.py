"""Regression tests for HITL draft identity and resumable publication."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.agents.collector import CollectStats
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

    async def test_new_digest_blocked_by_partial_publish_resends_buttons(self):
        state = BotState()
        state.set_pending("partial digest")
        state.published_chunks = 1
        state.save(self.settings.bot_state_file)
        draft_id = state.draft_id

        with patch.object(handlers.pipeline, "run_collect_and_digest") as collect:
            await handlers.send_digest_draft(self.bot, "123", self.settings)

        collect.assert_not_called()
        saved = BotState.load(self.settings.bot_state_file)
        self.assertEqual(saved.pending_digest, "partial digest")
        self.assertEqual(saved.published_chunks, 1)
        self.assertEqual(saved.draft_id, draft_id)
        self.bot.send_message.assert_awaited_once()
        kwargs = self.bot.send_message.await_args.kwargs
        self.assertEqual(kwargs["text"], handlers._PARTIAL_PUBLISH_PROMPT)
        self.assertEqual(
            kwargs["reply_markup"].inline_keyboard[0][0].callback_data,
            f"{HITL_CALLBACK_APPROVE}:{draft_id}",
        )

    async def test_cmd_digest_does_not_crash_when_partial_publish_pending(self):
        state = BotState()
        state.set_pending("partial digest")
        state.published_chunks = 1
        state.save(self.settings.bot_state_file)

        update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=123),
            message=SimpleNamespace(reply_text=AsyncMock()),
        )
        with patch.object(handlers.pipeline, "run_collect_and_digest") as collect:
            await handlers.cmd_digest(update, self.context)

        collect.assert_not_called()
        update.message.reply_text.assert_not_awaited()
        self.assertEqual(BotState.load(self.settings.bot_state_file).published_chunks, 1)
        self.bot.send_message.assert_awaited_once()

    async def test_corrupt_partial_state_allows_new_digest(self):
        state = BotState()
        state.published_chunks = 1
        state.pending_digest = ""
        state.draft_id = ""
        state.save(self.settings.bot_state_file)
        stats = CollectStats(added=1)

        with patch.object(
            handlers.pipeline,
            "run_collect_and_digest",
            return_value=("fresh digest", 1, {}, stats),
        ):
            await handlers.send_digest_draft(self.bot, "123", self.settings)

        saved = BotState.load(self.settings.bot_state_file)
        self.assertEqual(saved.pending_digest, "fresh digest")
        self.assertEqual(saved.published_chunks, 0)
        self.assertTrue(saved.draft_id)
        self.bot.send_message.assert_awaited()


if __name__ == "__main__":
    unittest.main()
