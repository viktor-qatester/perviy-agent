"""Career internship portals catalog for /internships."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

_INTERNSHIPS_TRIGGERS = frozenset(
    {
        "стажировки",
        "стажировка",
        "internships",
        "internship",
        "карьерные порталы",
        "порталы стажировок",
    }
)


def is_internships_request(text: str) -> bool:
    normalized = text.strip().lower().rstrip("?!.")
    return normalized in _INTERNSHIPS_TRIGGERS


def load_career_portals(path: Path) -> dict[str, list[dict[str, str]]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("career_portals.json must be a JSON object")
    return raw


def format_career_portals_message(data: dict[str, Any]) -> str:
    lines = ["<b>Карьерные порталы и программы стажировок</b>", ""]

    for category, portals in data.items():
        if not isinstance(portals, list):
            continue
        lines.append(f"<b>{html.escape(str(category))}</b>")
        for portal in portals:
            if not isinstance(portal, dict):
                continue
            name = html.escape(str(portal.get("name", "")).strip())
            url = str(portal.get("url", "")).strip()
            if not name or not url:
                continue
            lines.append(f'• <a href="{html.escape(url, quote=True)}">{name}</a>')
        lines.append("")

    lines.append("<i>Для вакансий в Беларуси: rabota.by и /digest.</i>")
    return "\n".join(lines).strip()


def build_internships_message(path: Path) -> str:
    if not path.is_file():
        return "Файл career_portals.json не найден. Обратитесь к администратору."
    try:
        data = load_career_portals(path)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        return f"Не удалось прочитать career_portals.json: {exc}"
    if not data:
        return "Список карьерных порталов пуст."
    return format_career_portals_message(data)
