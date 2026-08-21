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
    career_portals_file: Path = ROOT / "data" / "career_portals.json"
    bot_state_file: Path = ROOT / "data" / "bot_state.json"
    dry_run: bool = os.getenv("DRY_RUN", "true").lower() == "true"
    digest_days_ahead: int = int(os.getenv("DIGEST_DAYS_AHEAD", "7"))

    # Notifications: email, telegram или email,telegram
    notify_via: str = os.getenv("NOTIFY_VIA", "email,telegram")

    # Autonomous schedule (v0.4 — bot JobQueue)
    schedule_enabled: bool = os.getenv("SCHEDULE_ENABLED", "false").lower() == "true"
    schedule_days: str = os.getenv("SCHEDULE_DAYS", "tue,fri")
    schedule_time: str = (
        os.getenv("SCHEDULE_TIME")
        or os.getenv("SCHEDULE_RUN_TIME")
        or "05:00"
    )
    timezone: str = (
        os.getenv("TIMEZONE")
        or os.getenv("SCHEDULE_TIMEZONE")
        or "Europe/Moscow"
    )

    smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    email_user: str = os.getenv("EMAIL_USER", "")
    email_app_password: str = os.getenv("EMAIL_APP_PASSWORD", "")
    email_from: str = os.getenv("EMAIL_FROM", "")
    email_to: str = os.getenv("EMAIL_TO", "")

    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    # Личный чат: команды бота, черновик дайджеста, HITL-кнопки
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    # Публичный канал: публикация одобренного дайджеста (✅)
    telegram_channel_id: str | None = os.getenv("TELEGRAM_CHANNEL_ID", "").strip() or None
    # Telegram RSS (v0.3)
    telegram_rss_enabled: bool = os.getenv("TELEGRAM_RSS_ENABLED", "true").lower() == "true"
    telegram_rss_belarusitwant_url: str = os.getenv(
        "TELEGRAM_RSS_BELARUSITWANT_URL",
        "https://rsshub.rssforever.com/telegram/channel/belarusitwant",
    )

    # rabota.by (v0.3)
    rabota_by_enabled: bool = os.getenv("RABOTA_BY_ENABLED", "true").lower() == "true"
    rabota_by_area: str = os.getenv("RABOTA_BY_AREA", "1002")
    rabota_by_max_results: int = int(os.getenv("RABOTA_BY_MAX_RESULTS", "30"))

    # Habr Career (v0.4)
    habr_career_enabled: bool = os.getenv("HABR_CAREER_ENABLED", "true").lower() == "true"
    habr_career_max_results: int = int(os.getenv("HABR_CAREER_MAX_RESULTS", "30"))

    llm_enabled: bool = os.getenv("LLM_ENABLED", "true").lower() == "true"
    llm_provider: str = os.getenv("LLM_PROVIDER", "deepseek")  # deepseek | openai | gemini

    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    def authorized_chat_id(self) -> str:
        """TELEGRAM_CHAT_ID — кто может управлять ботом."""
        return self.telegram_chat_id.strip()

    def publish_channel_id(self) -> str | None:
        """TELEGRAM_CHANNEL_ID — куда публикуется одобренный дайджест."""
        channel = (self.telegram_channel_id or "").strip()
        return channel or None


settings = Settings()
