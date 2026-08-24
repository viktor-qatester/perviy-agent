"""HITL buttons must only act on the digest they were attached to."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.bot.state import BotState
from src.notifiers.telegram import hitl_callback_data, hitl_inline_keyboard, parse_hitl_callback


class HitlCallbackParseTests(unittest.TestCase):
    def test_roundtrip_nonce(self) -> None:
        data = hitl_callback_data("approve", "abc123def456")
        self.assertEqual(data, "hitl:approve:abc123def456")
        self.assertEqual(parse_hitl_callback(data), ("approve", "abc123def456"))

    def test_legacy_button_has_empty_nonce(self) -> None:
        self.assertEqual(parse_hitl_callback("hitl:approve"), ("approve", ""))
        self.assertEqual(parse_hitl_callback("hitl:edit"), ("edit", ""))
        self.assertEqual(parse_hitl_callback("hitl:cancel"), ("cancel", ""))

    def test_unknown_callback_is_rejected(self) -> None:
        self.assertIsNone(parse_hitl_callback("other:approve:abc"))
        self.assertIsNone(parse_hitl_callback(""))

    def test_keyboard_embeds_nonce_in_all_buttons(self) -> None:
        keyboard = hitl_inline_keyboard("deadbeef")
        payloads = [btn["callback_data"] for row in keyboard for btn in row]
        self.assertEqual(
            payloads,
            [
                "hitl:approve:deadbeef",
                "hitl:edit:deadbeef",
                "hitl:cancel:deadbeef",
            ],
        )

    def test_callback_data_fits_telegram_limit(self) -> None:
        data = hitl_callback_data("approve", "a" * 12)
        self.assertLessEqual(len(data.encode("utf-8")), 64)


class BotStateHitlTests(unittest.TestCase):
    def test_stale_nonce_does_not_match_current_draft(self) -> None:
        state = BotState()
        first = state.set_pending("digest A", pending_id="id-a")
        second = state.set_pending("digest B", pending_id="id-b")
        self.assertEqual(first, "id-a")
        self.assertEqual(second, "id-b")
        self.assertEqual(state.pending_digest, "digest B")
        self.assertTrue(state.matches_hitl_nonce("id-b"))
        self.assertFalse(state.matches_hitl_nonce("id-a"))
        self.assertFalse(state.matches_hitl_nonce(""))

    def test_legacy_state_without_pending_id_never_matches(self) -> None:
        state = BotState(pending_digest="old draft", pending_id="")
        self.assertFalse(state.matches_hitl_nonce(""))
        self.assertFalse(state.matches_hitl_nonce("anything"))

    def test_clear_pending_drops_nonce(self) -> None:
        state = BotState()
        state.set_pending("draft", pending_id="nonce-1")
        state.clear_pending()
        self.assertEqual(state.pending_digest, "")
        self.assertEqual(state.pending_id, "")
        self.assertFalse(state.matches_hitl_nonce("nonce-1"))

    def test_load_missing_pending_id_defaults_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bot_state.json"
            path.write_text(
                json.dumps({"pending_digest": "draft", "mode": None, "updated_at": ""}),
                encoding="utf-8",
            )
            loaded = BotState.load(path)
        self.assertEqual(loaded.pending_digest, "draft")
        self.assertEqual(loaded.pending_id, "")
        self.assertFalse(loaded.matches_hitl_nonce(""))


if __name__ == "__main__":
    unittest.main()
