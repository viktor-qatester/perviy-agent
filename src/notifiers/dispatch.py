"""Route digest to configured notification channels."""

from __future__ import annotations

from datetime import datetime

from src.bot.state import BotState
from src.config import Settings
from src.notifiers.email import send_email
from src.notifiers.telegram import send_telegram_hitl_draft, send_telegram_message


def deliver_digest(
    settings: Settings,
    digest: str,
    *,
    dry_run: bool,
    hitl: bool = False,
) -> dict[str, str | None]:
    """Send digest via email and/or Telegram. Returns per-channel status."""
    title = _digest_subject()
    body = f"{title}\n\n{digest}"
    results: dict[str, str | None] = {"email": None, "telegram": None}

    if dry_run:
        print(f"=== {title} ===")
        print(digest)
        if hitl:
            print("[HITL] Кнопки ✅/✏️/❌ будут в Telegram при --send.")
        print("[DRY RUN] Email/Telegram не отправлены.")
        return results

    channels = {c.strip().lower() for c in settings.notify_via.split(",") if c.strip()}

    if "email" in channels:
        try:
            send_email(
                subject=title,
                body=body,
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                username=settings.email_user,
                password=settings.email_app_password,
                mail_from=settings.email_from,
                mail_to=settings.email_to,
                use_tls=settings.smtp_use_tls,
            )
            results["email"] = "ok"
            print(f"Email отправлен: {settings.email_to}")
        except Exception as exc:  # noqa: BLE001
            results["email"] = str(exc)
            print(f"Email ошибка: {exc}")

    if "telegram" in channels:
        try:
            if hitl:
                send_telegram_hitl_draft(
                    token=settings.telegram_bot_token,
                    chat_id=settings.telegram_chat_id,
                    title=title,
                    digest=digest,
                )
                state = BotState.load(settings.bot_state_file)
                state.set_pending(digest)
                state.save(settings.bot_state_file)
            else:
                send_telegram_message(
                    token=settings.telegram_bot_token,
                    chat_id=settings.telegram_chat_id,
                    text=body,
                )
            results["telegram"] = "ok"
            print("Telegram отправлен.")
        except Exception as exc:  # noqa: BLE001
            results["telegram"] = str(exc)
            print(f"Telegram ошибка: {exc}")

    return results


def _digest_subject() -> str:
    today = datetime.now().strftime("%d.%m.%Y")
    return f"IT-события BY — {today}"
