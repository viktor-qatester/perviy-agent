# Расписание и перенос на AEZA

Цель: одна автоматическая рассылка в понедельник и четверг. Задание стартует
в 05:00 Europe/Minsk; черновик приходит после окончания сбора (обычно через
минуты, не в ту же секунду). Перезапуск контейнера после 05:00 в день рассылки
пропускает этот запуск до следующего пн/чт. `misfire_grace_time` 15 минут
спасает только занятый цикл уже работающего процесса, а не старт после 05:00.

Единственный автоматический отправитель — `python src/main.py --bot` на AEZA:
черновик с кнопками одобрения в `TELEGRAM_CHAT_ID`. `DRY_RUN=true` блокирует
только CLI `python src/main.py` без `--send`; автосбор и `/digest` всё равно
пишут в Telegram.

В GitHub Actions нет `schedule`. Workflow «IT digest» отключён вручную (13.10);
повторно не включать и не нажимать Run workflow: `workflow_dispatch` шлёт
готовый отчёт без кнопок, это другой формат и второй отправитель.

## Текущее состояние (2026-10-13, до переключения)

| Где | Факт | Расписание |
| --- | --- | --- |
| GitHub Actions | workflow «IT digest» disabled | нет |
| FORNEX | `qa_bot.service` active+enabled, `/root/qa_bot`, EnvironmentFile=`/root/qa_bot/.env` | в `.env` `tue,fri`, старый код фактически пн/чт 05:00; 12.10 sendMessage HTTP 200 в 05:01 |
| AEZA | код в `/srv/vic-workspace/bots/qa_bot`, контейнер не запущен | в `.env` `SCHEDULE_ENABLED=true`, `DRY_RUN=true`; не стартовать, пока код не обновлён |
| Токен | раскрыт в журнале FORNEX | перевыпуск ещё не сделан |
| PR | [#16](https://github.com/viktor-qatester/perviy-agent/pull/16) draft | не сливать до переключения |

## Целевые настройки `.env` на AEZA

Менять только эти строки (скрипт или точечная правка). Токены не печатать.

```dotenv
SCHEDULE_ENABLED=true
SCHEDULE_DAYS=mon,thu
SCHEDULE_TIME=05:00
TIMEZONE=Europe/Minsk
```

Удалить `SCHEDULE_RUN_TIME` и `SCHEDULE_TIMEZONE`. Права `.env` — `0600`.

## Порядок переключения

Не запускать контейнер на AEZA, пока FORNEX не остановлен. Иначе два polling.

### 1. Резервные копии (FORNEX ещё работает)

Права архивов `0600`, не смотреть содержимое `.env`.

- AEZA: tar каталога `/srv/vic-workspace/bots/qa_bot` (включая `.env` и `data/`)
  в `/srv/vic-workspace/backups/qa_bot-<дата>/` плюс SHA256.
- FORNEX: tar `/root/qa_bot` и копия `/etc/systemd/system/qa_bot.service`
  в отдельный архив плюс SHA256.

### 2. Код и compose на AEZA (контейнер всё ещё down)

```bash
cd /srv/vic-workspace/bots/qa_bot
git fetch origin
git merge --ff-only origin/main   # после merge PR; до merge: origin/fix/aeza-mon-thu-schedule
```

`Dockerfile.vic` и `compose.vic.yaml` не в Git. В compose: `restart: unless-stopped`,
`container_name: vic-qa-bot`. Собрать образ, контейнер не поднимать:

```bash
docker compose -f compose.vic.yaml build
```

### 3. Проверка расписания без отправки и без polling

```bash
docker compose -f compose.vic.yaml run --rm --no-deps app python -m unittest discover -s tests
docker compose -f compose.vic.yaml run --rm --no-deps app python scripts/check_schedule.py --expect-days mon,thu
```

Ожидаются только `Mon`/`Thu` в `05:00 +0300`. Ближайшие даты от 13.10.2026:
чт 15.10, пн 19.10, чт 22.10, пн 26.10, чт 29.10, пн 02.11. Сеть и `send_*`
скрипт не вызывает.

### 4. Остановить FORNEX

```bash
systemctl stop qa_bot.service
systemctl disable qa_bot.service
systemctl is-active qa_bot.service    # inactive
systemctl is-enabled qa_bot.service   # disabled
```

Каталог `/root/qa_bot` и unit-файл не удалять.

### 5. Финальная синхронизация `data/` (обязательно после stop)

Копия до остановки не годится: FORNEX мог обновить `bot_state.json` / `events.json`.

С FORNEX на AEZA, только `data/` (`bot_state.json`, `events.json`,
`manual_events.json`, `career_portals.json` и остальные файлы там). После
распаковки на AEZA сверить размер и mtime с FORNEX. `.env` этим шагом не копировать.

### 6. Перевыпуск токена (делает владелец в @BotFather)

`/revoke`. Старый токен из журнала перестаёт работать. До этого шага новый
токен никуда не записывать.

### 7. Записать новый токен без экрана и истории

Нужен TTY (`ssh -t`). Скрипт читает значение скрытым вводом, не печатает его,
меняет только одну строку, кладёт `.env.bak-<время>` с режимом `0600`.

```bash
# AEZA
ssh -t -i ... root@77.110.101.123 \
  'bash /srv/vic-workspace/bots/qa_bot/scripts/set_env_secret.sh /srv/vic-workspace/bots/qa_bot/.env TELEGRAM_BOT_TOKEN --verify'
# FORNEX (сервис не запускать; нужно для отката). Скрипт можно скопировать без обновления кода бота.
ssh -t ... root@31.172.78.193 \
  'bash /root/qa_bot/scripts/set_env_secret.sh /root/qa_bot/.env TELEGRAM_BOT_TOKEN'
```

`--verify` вызывает только `getMe` (сообщение не отправляется). Ожидание:
`getMe: ok @<имя_бота>`. Секрет `TELEGRAM_BOT_TOKEN` в GitHub — вручную в
настройках репозитория, после перевыпуска; `gh` и печать секрета не использовать.

### 8. Запуск только AEZA

Завершить до чт 15.10 05:00 Europe/Minsk. Не стартовать между 05:00 и ~05:15
в день рассылки: этот запуск будет пропущен.

```bash
cd /srv/vic-workspace/bots/qa_bot
docker compose -f compose.vic.yaml up -d
```

### 9. Проверка после запуска

- `docker ps --filter name=vic-qa-bot` — ровно один контейнер;
- FORNEX: `inactive` / `disabled`;
- в `docker logs vic-qa-bot` есть
  `Schedule enabled: mon,thu at 05:00 (Europe/Minsk), days=(1, 4)`;
- нет `Conflict` (второй polling) и нет подстроки `bot` + цифры + `:`;
- есть фильтр токена: искусственный токен в тесте, не боевой.

Первая живая проверка доставки — чт 15.10: в логе
`Scheduled digest: starting collect pipeline`, затем
`Digest draft delivered: scheduled=True ...`. Сообщение в чате — черновик
с кнопками, не готовый канал.

## Откат

1. AEZA: `docker compose -f compose.vic.yaml down` (`data/` на диске остаётся).
2. Скопировать актуальный `data/` с AEZA на FORNEX.
3. Новый токен уже должен быть в `/root/qa_bot/.env` (шаг 7). Не возвращать
   раскрытый токен.
4. Старый код FORNEX: оставить `SCHEDULE_DAYS=tue,fri` (фактически пн/чт).
   `mon,thu` на старом коде даст вс/ср. Либо сначала обновить код и тогда `mon,thu`.
5. `systemctl enable --now qa_bot.service`, смотреть журнал без `cat .env`.

Аварийный ручной отчёт: включить workflow «IT digest» и Run workflow — это
готовый текст без кнопок, не штатный путь.

## Логи

`run_bot` поднимает `httpx`/`httpcore` до WARNING, маскирует токен в записях
и в traceback при стартовой ошибке. Журналы FORNEX до `/revoke` содержат
старый токен; после отзыва он бесполезен. Чистить journald не обязательно.
