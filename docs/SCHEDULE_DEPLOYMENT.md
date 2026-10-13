# Расписание и развёртывание на AEZA

Цель: одна автоматическая рассылка в понедельник и четверг, 05:00 Europe/Minsk.
Единственный автоматический отправитель — бот `python src/main.py --bot` на AEZA
(черновик с кнопками одобрения в `TELEGRAM_CHAT_ID`). В GitHub Actions нет
`schedule`; `workflow_dispatch` отправляет отчёт только при ручном запуске.
Сервис `qa_bot.service` на FORNEX остановлен и выключен, каталог сохранён для отката.

## Окружения

| Где | Каталог | Запуск | Расписание |
| --- | --- | --- | --- |
| AEZA | `/srv/vic-workspace/bots/qa_bot` | `docker compose -f compose.vic.yaml` | `SCHEDULE_ENABLED=true` |
| FORNEX | `/root/qa_bot` | `qa_bot.service` | выключен (откат) |
| GitHub Actions | — | только вручную | нет |

## Настройки `.env` на AEZA

Изменять только эти строки, остальные поля и права `0600` сохранить:

```dotenv
SCHEDULE_ENABLED=true
SCHEDULE_DAYS=mon,thu
SCHEDULE_TIME=05:00
TIMEZONE=Europe/Minsk
```

Устаревшие `SCHEDULE_RUN_TIME` и `SCHEDULE_TIMEZONE` удалить: `SCHEDULE_TIME` и
`TIMEZONE` имеют приоритет. Не публиковать `.env` и не выводить окружение с токенами.

## Порядок переключения

1. Резервные копии с SHA256, права `0600`:
   - AEZA: каталог `qa_bot` целиком, включая `.env` и `data/`;
   - FORNEX: `/root/qa_bot` и `/etc/systemd/system/qa_bot.service`.
2. Перенести актуальный `data/` с FORNEX на AEZA (`bot_state.json`, `events.json`,
   `manual_events.json`, `career_portals.json`).
3. На AEZA обновить код до `main` (`git fetch` + `git merge --ff-only`). Локальные
   `Dockerfile.vic`, `compose.vic.yaml` не в Git и не перезаписываются.
   В `compose.vic.yaml`: `restart: unless-stopped`, `container_name: vic-qa-bot`.
4. Собрать образ и проверить расписание без отправки и без polling:

   ```bash
   docker compose -f compose.vic.yaml build
   docker compose -f compose.vic.yaml run --rm --no-deps app python -m unittest discover -s tests
   docker compose -f compose.vic.yaml run --rm --no-deps app python -c '
   from datetime import datetime, timedelta
   from types import SimpleNamespace
   from zoneinfo import ZoneInfo
   from telegram.ext import JobQueue
   from src.bot.schedule import setup_schedule
   from src.config import settings
   q = JobQueue(); setup_schedule(SimpleNamespace(job_queue=q), settings)
   job, = q.scheduler.get_jobs()
   now, prev = datetime.now(ZoneInfo(settings.timezone)), None
   for _ in range(6):
       prev = job.trigger.get_next_fire_time(prev, now); print(prev.strftime("%a %Y-%m-%d %H:%M %z"))
       now = prev + timedelta(seconds=1)
   '
   ```

   Ожидается только `Mon`/`Thu` в `05:00 +0300`.
5. FORNEX: `systemctl stop qa_bot.service && systemctl disable qa_bot.service`.
6. Перевыпустить токен в @BotFather (`/revoke`). Старый токен перестаёт работать,
   поэтому старые копии больше не могут отправлять и опрашивать Telegram.
7. Записать новый токен в `.env` на AEZA без истории shell и без вывода на экран
   (`read -rs`), обновить секрет `TELEGRAM_BOT_TOKEN` в GitHub через настройки репозитория.
8. Запустить: `docker compose -f compose.vic.yaml up -d`.
9. Проверить:
   - `docker ps --filter name=qa` — ровно один контейнер `vic-qa-bot`;
   - FORNEX: `systemctl is-active qa_bot.service` → `inactive`, `is-enabled` → `disabled`;
   - `docker logs vic-qa-bot` содержит `Schedule enabled: mon,thu at 05:00 (Europe/Minsk), days=(1, 4)`;
   - в логах нет `Conflict` (второй polling) и нет строк вида `bot<цифры>:`.

## Откат

1. AEZA: `docker compose -f compose.vic.yaml down` (данные остаются в `data/`).
2. Вернуть `data/` на FORNEX, записать новый токен в `/root/qa_bot/.env`.
3. На FORNEX старый код: в нём `tue,fri` срабатывает в понедельник и четверг.
   Либо оставить `SCHEDULE_DAYS=tue,fri`, либо сначала обновить код до `main`
   и указать `mon,thu`.
4. `systemctl enable --now qa_bot.service`, проверить журнал.

## Логи

`run_bot` поднимает уровень `httpx`/`httpcore` до WARNING и маскирует токен
во всех записях. Журналы, записанные до перевыпуска, содержат старый токен:
после `/revoke` он недействителен.
