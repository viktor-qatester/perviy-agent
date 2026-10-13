"""The automatic digest is an approval draft, independent of DRY_RUN."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from telegram import InlineKeyboardMarkup

from src.bot import handlers
from src.bot.schedule import scheduled_digest_job
from src.bot.state import BotState
from src.notifiers.telegram import (
    HITL_CALLBACK_APPROVE,
    HITL_CALLBACK_CANCEL,
    HITL_CALLBACK_EDIT,
)

ADMIN_CHAT = "123"
CHANNEL = "-100456"


class ScheduledDraftTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.settings = SimpleNamespace(
            dry_run=True,  # must not suppress the draft
            bot_state_file=Path(temp.name) / "state.json",
            authorized_chat_id=lambda: ADMIN_CHAT,
            publish_channel_id=lambda: CHANNEL,
        )
        self.bot = SimpleNamespace(send_message=AsyncMock())
        self.context = SimpleNamespace(
            bot=self.bot,
            application=SimpleNamespace(bot_data={"settings": self.settings}),
        )
        stats = Mock(added=2, skipped_duplicate=0)
        self.collect = patch.object(
            handlers.pipeline, "run_collect_and_digest",
            return_value=("digest body", 5, {}, stats),
        )

    async def test_dry_run_true_still_sends_draft_with_approval_buttons(self):
        with self.collect, self.assertLogs("src.bot.handlers", "INFO") as logs:
            await scheduled_digest_job(self.context)

        self.bot.send_message.assert_awaited_once()
        kwargs = self.bot.send_message.await_args.kwargs
        self.assertEqual(kwargs["chat_id"], ADMIN_CHAT)
        self.assertIn("digest body", kwargs["text"])

        markup = kwargs["reply_markup"]
        self.assertIsInstance(markup, InlineKeyboardMarkup)
        callbacks = [b.callback_data for b in markup.inline_keyboard[0]]
        state = BotState.load(self.settings.bot_state_file)
        self.assertTrue(state.draft_id)
        self.assertEqual(state.pending_digest, "digest body")
        self.assertEqual(callbacks, [
            f"{HITL_CALLBACK_APPROVE}:{state.draft_id}",
            f"{HITL_CALLBACK_EDIT}:{state.draft_id}",
            f"{HITL_CALLBACK_CANCEL}:{state.draft_id}",
        ])
        self.assertTrue(any("Digest draft delivered" in line for line in logs.output))

    async def test_automatic_run_never_publishes_to_channel(self):
        with self.collect:
            await scheduled_digest_job(self.context)
        targets = {call.kwargs["chat_id"] for call in self.bot.send_message.await_args_list}
        self.assertEqual(targets, {ADMIN_CHAT})

    async def test_collection_failure_notifies_admin_only(self):
        broken = patch.object(handlers.pipeline, "run_collect_and_digest",
                              side_effect=RuntimeError("sources down"))
        with broken, self.assertLogs("src.bot.schedule", "ERROR"):
            await scheduled_digest_job(self.context)
        self.bot.send_message.assert_awaited_once()
        self.assertEqual(self.bot.send_message.await_args.kwargs["chat_id"], ADMIN_CHAT)
        self.assertFalse(BotState.load(self.settings.bot_state_file).pending_digest)


if __name__ == "__main__":
    unittest.main()
