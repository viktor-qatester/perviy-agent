"""
Первый Агент — точка входа.

Usage:
  python src/main.py --dry-run
  python src/main.py --ask "митапы на этой неделе"
  python src/main.py --send          # реальная отправка (email + telegram)
  python src/main.py --test-notify   # тест уведомлений без сбора данных
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# allow `python src/main.py` from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.collector import collect, save_events
from src.agents.digest import build_digest
from src.agents.support import answer
from src.config import settings
from src.notifiers.dispatch import deliver_digest
from src.sources.manual_feed import ManualFeedSource


def write_run_log(payload: dict) -> Path:
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = settings.logs_dir / f"run-{stamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_pipeline(*, dry_run: bool) -> int:
    sources = [ManualFeedSource(settings.manual_feed)]
    events, errors = collect(sources)

    save_events(settings.events_file, events)
    digest = build_digest(events, days=settings.digest_days_ahead)

    notify_results = deliver_digest(settings, digest, dry_run=dry_run)

    log_path = write_run_log(
        {
            "started_at": datetime.now(timezone.utc).astimezone().isoformat(),
            "sources_ok": [s.name for s in sources if s.name not in errors],
            "sources_failed": errors,
            "events_found": len(events),
            "digest_preview": digest[:500],
            "dry_run": dry_run,
            "notify": notify_results,
        }
    )

    print(f"Сохранено событий: {len(events)} -> {settings.events_file}")
    print(f"Лог прогона: {log_path}")
    if errors:
        print("Ошибки источников:", errors)
        return 1
    return 0


def test_notify() -> int:
    sample = (
        "Тестовое сообщение от Первого Агента.\n\n"
        "Если вы видите это письмо или сообщение в Telegram — "
        "уведомления настроены правильно."
    )
    results = deliver_digest(settings, sample, dry_run=False)
    failed = [k for k, v in results.items() if v and v != "ok"]
    if failed:
        print("Не все каналы сработали:", results)
        return 1
    print("Тест уведомлений прошёл успешно:", results)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Первый Агент — мониторинг событий BY")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Только консоль, без email/Telegram",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Отправить дайджест на email и в Telegram",
    )
    parser.add_argument("--ask", type=str, help="Support-режим: задать вопрос")
    parser.add_argument(
        "--test-notify",
        action="store_true",
        help="Тест email/Telegram без сбора событий",
    )
    args = parser.parse_args()

    if args.test_notify:
        return test_notify()

    if args.ask:
        sources = [ManualFeedSource(settings.manual_feed)]
        events, _ = collect(sources)
        print(answer(args.ask, events, days=settings.digest_days_ahead))
        return 0

    if args.send:
        dry_run = False
    elif args.dry_run is True:
        dry_run = True
    else:
        dry_run = settings.dry_run

    return run_pipeline(dry_run=dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
