"""Configuration from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    data_dir: Path = ROOT / "data"
    logs_dir: Path = ROOT / "logs"
    events_file: Path = ROOT / "data" / "events.json"
    manual_feed: Path = ROOT / "data" / "manual_events.json"
    dry_run: bool = os.getenv("DRY_RUN", "true").lower() == "true"
    digest_days_ahead: int = int(os.getenv("DIGEST_DAYS_AHEAD", "7"))

    # Notifications: email, telegram или email,telegram
    notify_via: str = os.getenv("NOTIFY_VIA", "email,telegram")
    schedule_run_time: str = os.getenv("SCHEDULE_RUN_TIME", "05:00")
    schedule_timezone: str = os.getenv("SCHEDULE_TIMEZONE", "Europe/Minsk")

    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    email_user: str = os.getenv("EMAIL_USER", "")
    email_app_password: str = os.getenv("EMAIL_APP_PASSWORD", "")
    email_from: str = os.getenv("EMAIL_FROM", "")
    email_to: str = os.getenv("EMAIL_TO", "")

    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")


settings = Settings()
