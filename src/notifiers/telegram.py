"""Telegram notifications (personal chat or channel)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

HITL_CALLBACK_APPROVE = "hitl:approve"
HITL_CALLBACK_EDIT = "hitl:edit"
HITL_CALLBACK_CANCEL = "hitl:cancel"

HITL_KEYBOARD: list[list[dict[str, str]]] = [
    [
        {"text": "✅ Опубликовать", "callback_data": HITL_CALLBACK_APPROVE},
        {"text": "✏️ Править", "callback_data": HITL_CALLBACK_EDIT},
        {"text": "❌ Отмена", "callback_data": HITL_CALLBACK_CANCEL},
    ]
]


def send_telegram_message(*, token: str, chat_id: str, text: str) -> None:
    if not token or not chat_id:
        raise ValueError("Telegram: заполните TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID в .env")

    for chunk in _split_text(text, limit=4000):
        _post_message(token=token, chat_id=chat_id, text=chunk)


def send_telegram_hitl_draft(*, token: str, chat_id: str, title: str, digest: str) -> None:
    """Send digest draft with HITL inline keyboard on the last chunk."""
    body = f"{title}\n\n{digest}"
    chunks = _split_text(body, limit=4000)
    for index, chunk in enumerate(chunks):
        reply_markup = HITL_KEYBOARD if index == len(chunks) - 1 else None
        _post_message(token=token, chat_id=chat_id, text=chunk, reply_markup=reply_markup)


def _post_message(
    *,
    token: str,
    chat_id: str,
    text: str,
    reply_markup: list[list[dict[str, str]]] | None = None,
) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = {"inline_keyboard": reply_markup}

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API error: {body}") from exc

    if not data.get("ok"):
        raise RuntimeError(f"Telegram API rejected message: {data}")


def _telegram_len(text: str) -> int:
    """Telegram message length is UTF-16 code units, not Python code points."""
    return len(text.encode("utf-16-le")) // 2


def _append_chunk(parts: list[str], chunk: str) -> None:
    stripped = chunk.rstrip()
    if stripped:
        parts.append(stripped)


def _chunks_by_telegram_len(text: str, limit: int) -> list[str]:
    """Slice `text` so each piece is at most `limit` UTF-16 code units."""
    parts: list[str] = []
    start = 0
    used = 0
    for index, char in enumerate(text):
        units = 2 if ord(char) > 0xFFFF else 1
        if used + units > limit:
            _append_chunk(parts, text[start:index])
            start = index
            used = units
        else:
            used += units
    _append_chunk(parts, text[start:])
    return parts


def _split_text(text: str, limit: int) -> list[str]:
    if _telegram_len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if _telegram_len(line) > limit:
            if current:
                _append_chunk(parts, current)
                current = ""
            parts.extend(_chunks_by_telegram_len(line, limit))
            continue
        if _telegram_len(current) + _telegram_len(line) > limit:
            _append_chunk(parts, current)
            current = line
        else:
            current += line
    if current.strip():
        _append_chunk(parts, current)
    return parts or _chunks_by_telegram_len(text, limit) or [""]


def send_draft(title: str, body: str, *, dry_run: bool = True) -> None:
    """Legacy console helper used by main pipeline."""
    message = f"=== {title} ===\n{body}\n"
    if dry_run:
        print(message)
        print("[DRY RUN] Сообщение не отправлено. Настройте NOTIFY_* в .env")
    else:
        print(message)
