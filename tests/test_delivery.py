"""Regression tests for the scheduled digest path."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src import main
from src.bot.schedule import parse_schedule_days
from src.config import Settings
from src.notifiers.dispatch import deliver_digest


class ScheduleTests(unittest.TestCase):
    def test_tuesday_and_friday_defaults(self):
        self.assertEqual(parse_schedule_days(Settings().schedule_days), (1, 4))
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/daily-digest.yml").read_text(encoding="utf-8")
        self.assertIn('cron: "0 2 * * 2,5"', workflow)


class DeliveryTests(unittest.TestCase):
    def test_cli_send_uses_direct_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = SimpleNamespace(
                logs_dir=Path(temp) / "logs",
                events_file=Path(temp) / "events.json",
                digest_days_ahead=7,
            )
            stats = Mock(added=1, skipped_duplicate=0, kept_existing=0)
            stats.to_dict.return_value = {"added": 1}
            source = SimpleNamespace(name="source")
            with (
                patch.object(main, "settings", settings),
                patch.object(main, "build_source_list", return_value=[source]),
                patch.object(main, "collect", return_value=([], {}, stats)),
                patch.object(main, "save_events"),
                patch.object(main, "build_digest", return_value="digest"),
                patch.object(main, "deliver_digest", return_value={"telegram": "ok"}) as delivery,
            ):
                self.assertEqual(main.run_pipeline(dry_run=False), 0)
            delivery.assert_called_once_with(settings, "digest", dry_run=False)

    def test_direct_telegram_delivery_does_not_create_pending_draft(self):
        settings = SimpleNamespace(
            notify_via="telegram",
            telegram_bot_token="token",
            telegram_chat_id="123",
            bot_state_file=Path("unused.json"),
        )
        with (
            patch("src.notifiers.dispatch.send_telegram_message") as send,
            patch("src.notifiers.dispatch.BotState.load", side_effect=AssertionError("state must not be used")),
        ):
            result = deliver_digest(settings, "digest", dry_run=False)
        self.assertEqual(result["telegram"], "ok")
        send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
