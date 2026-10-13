"""scripts/set_env_secret.sh replaces one key safely (fake values only)."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "set_env_secret.sh"
OLD = "1111111111:AAOldFakeTokenForTests_only-000000"
NEW = "2222222222:AANewFakeTokenForTests_only-111111"


def _bash() -> str | None:
    bash = shutil.which("bash")
    if not bash:
        return None
    try:
        ok = subprocess.run([bash, "-c", "echo ok"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return bash if ok.returncode == 0 and ok.stdout.strip() == "ok" else None


BASH = _bash()


@unittest.skipUnless(os.name != "nt" and BASH, "set_env_secret.sh runs on Linux VPS (AEZA/FORNEX)")
class SetEnvSecretTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.env_file = Path(temp.name) / ".env"
        self.env_file.write_text(
            "NOTIFY_VIA=telegram\n"
            f"TELEGRAM_BOT_TOKEN={OLD}\n"
            "TELEGRAM_CHAT_ID=42\n"
            "SCHEDULE_DAYS=mon,thu",  # no trailing newline on purpose
            encoding="utf-8",
        )
        os.chmod(self.env_file, 0o600)

    def run_script(self, *lines, key="TELEGRAM_BOT_TOKEN"):
        return subprocess.run(
            [BASH, SCRIPT.as_posix(), self.env_file.as_posix(), key, "--stdin"],
            input="".join(f"{line}\n" for line in lines),
            capture_output=True, text=True, timeout=30,
        )

    def test_replaces_only_the_token_and_never_prints_it(self):
        result = self.run_script(NEW, NEW)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.env_file.read_text(encoding="utf-8").splitlines(),
            ["NOTIFY_VIA=telegram", f"TELEGRAM_BOT_TOKEN={NEW}",
             "TELEGRAM_CHAT_ID=42", "SCHEDULE_DAYS=mon,thu"],
        )
        for secret in (NEW, OLD):
            self.assertNotIn(secret, result.stdout + result.stderr)
        backups = list(self.env_file.parent.glob(".env.bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertIn(OLD, backups[0].read_text(encoding="utf-8"))
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(self.env_file.stat().st_mode), 0o600)
        self.assertFalse(list(self.env_file.parent.glob(".env.??????")))

    def test_mismatch_changes_nothing(self):
        before = self.env_file.read_text(encoding="utf-8")
        result = self.run_script(NEW, NEW + "x")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.env_file.read_text(encoding="utf-8"), before)
        self.assertEqual(list(self.env_file.parent.glob(".env.bak-*")), [])
        self.assertNotIn(NEW, result.stdout + result.stderr)

    def test_rejects_value_that_is_not_a_telegram_token(self):
        before = self.env_file.read_text(encoding="utf-8")
        result = self.run_script("short", "short")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.env_file.read_text(encoding="utf-8"), before)

    def test_requires_a_terminal_without_stdin_flag(self):
        result = subprocess.run(
            [BASH, SCRIPT.as_posix(), self.env_file.as_posix(), "TELEGRAM_BOT_TOKEN"],
            input=f"{NEW}\n{NEW}\n", capture_output=True, text=True, timeout=30,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(OLD, self.env_file.read_text(encoding="utf-8"))

    def test_appends_missing_key(self):
        result = self.run_script("fake_value_123", "fake_value_123", key="OTHER_SECRET")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OTHER_SECRET=fake_value_123", self.env_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
