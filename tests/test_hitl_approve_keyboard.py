"""HITL approve must publish even if keyboard removal fails."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.bot.handlers import on_callback
from src.bot.state import BotState
from src.config import Settings
from src.notifiers.telegram import HITL_CALLBACK_APPROVE, HITL_CALLBACK_CANCEL


def _settings(tmp: Path) -> Settings:
    return Settings(
        logs_dir=tmp / "logs",
        bot_state_file=tmp / "bot_state.json",
        telegram_chat_id="1001",
        telegram_channel_id="@digest_channel",
    )


def _update(*, chat_id: int = 1001, data: str) -> MagicMock:
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_reply_markup = AsyncMock(
        side_effect=RuntimeError("Bad Request: message can't be edited")
    )
    query.message.reply_text = AsyncMock()

    update = MagicMock()
    update.callback_query = query
    update.effective_chat.id = chat_id
    return update


class HitlApproveKeyboardTests(unittest.IsolatedAsyncioTestCase):
    async def test_approve_publishes_when_keyboard_edit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            settings = _settings(tmp)
            state = BotState()
            state.set_pending("QA intern — набор открыт\nhttps://rabota.by/vacancy/1")
            state.save(settings.bot_state_file)

            update = _update(data=HITL_CALLBACK_APPROVE)
            context = MagicMock()
            context.bot_data = {"settings": settings}
            context.bot.send_message = AsyncMock()

            await on_callback(update, context)

            context.bot.send_message.assert_awaited()
            sent = context.bot.send_message.await_args
            self.assertEqual(sent.kwargs["chat_id"], "@digest_channel")
            self.assertIn("QA intern", sent.kwargs["text"])
            update.callback_query.message.reply_text.assert_awaited()
            self.assertIn("опубликован", update.callback_query.message.reply_text.await_args.args[0])

            reloaded = BotState.load(settings.bot_state_file)
            self.assertEqual(reloaded.pending_digest, "")

    async def test_cancel_confirms_when_keyboard_edit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            settings = _settings(tmp)
            state = BotState()
            state.set_pending("draft")
            state.save(settings.bot_state_file)

            update = _update(data=HITL_CALLBACK_CANCEL)
            context = MagicMock()
            context.bot_data = {"settings": settings}
            context.bot.send_message = AsyncMock()

            await on_callback(update, context)

            context.bot.send_message.assert_not_awaited()
            update.callback_query.message.reply_text.assert_awaited_once()
            self.assertIn("отменён", update.callback_query.message.reply_text.await_args.args[0])
            reloaded = BotState.load(settings.bot_state_file)
            self.assertEqual(reloaded.pending_digest, "")


if __name__ == "__main__":
    unittest.main()
