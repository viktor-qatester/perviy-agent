# Первый агент: состояние расписания

## Решение

Понедельник и четверг, задание в 05:00 Europe/Minsk. Вторник и пятница не
используются. Доставка черновика — после сбора, не «ровно в 05:00».
Единственный автоматический отправитель после переноса — бот `--bot` на AEZA
(черновик с кнопками). `DRY_RUN` этот путь не выключает.

## Снимок 2026-10-13 (переключение не начато)

- PR [#16](https://github.com/viktor-qatester/perviy-agent/pull/16) draft,
  ветка `fix/aeza-mon-thu-schedule`. Не сливать до переноса.
- GitHub workflow «IT digest» вручную disabled. Не включать и не жать Run.
- FORNEX: `qa_bot.service` active+enabled, каталог `/root/qa_bot`.
  `.env`: `SCHEDULE_ENABLED=true`, `SCHEDULE_DAYS=tue,fri`, `DRY_RUN=true`.
  Старый код: фактически пн/чт 05:00; 12.10 в 05:01 Telegram принял sendMessage.
- AEZA: файлы есть, контейнер не запущен. Не стартовать параллельно с FORNEX.
- Токен раскрыт в журнале FORNEX. Перевыпуск не выполнен.

## Код в этой ветке

- `SCHEDULE_DAYS` по умолчанию `mon,thu` (JobQueue: Sunday=0 → mon=1, thu=4).
- Schedule убран из `.github/workflows/daily-digest.yml`.
- Токен маскируется в логах; `httpx`/`httpcore` на WARNING; старт с
  `InvalidToken` не печатает токен в stderr.
- Автосбор вызывает `send_digest_draft(..., scheduled=True)` независимо от `DRY_RUN`.
- `misfire_grace_time` 15 мин; рестарт после 05:00 пропускает день.
- `scripts/check_schedule.py` — даты без сети и отправки.
- `scripts/set_env_secret.sh` — скрытый ввод одного ключа в `.env`.

## Исправление 2026-10-02

`JobQueue.run_daily` в python-telegram-bot >=20: Sunday=0. Старые 1,4 давали
пн/чт при записи `tue,fri`.

## Оставшиеся шаги владельца

По `docs/SCHEDULE_DEPLOYMENT.md`: резервные копии → код на AEZA без запуска →
проверка дат → stop+disable FORNEX → финальная копия `data/` → `/revoke` →
новый токен на AEZA и FORNEX (FORNEX не запускать) → `up -d` на AEZA до
чт 15.10 05:00. Секрет GitHub — вручную после перевыпуска.
