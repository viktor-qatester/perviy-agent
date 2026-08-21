# Источники: стажировки и митапы (Беларусь)

MVP начинаем с **ручного feed** — потом подключаем живые источники по одному.

---

## Правило безопасности (обязательно)

**СТРОГИЙ ЗАПРЕТ БЕЗОПАСНОСТИ:** Никогда и ни при каких условиях не добавлять, не парсить, не упоминать и не генерировать ссылки/названия доменов dev[.]by, devby[.]io и связанных с ними Telegram-ресурсов. Использовать для вакансий и стажировок исключительно нейтральные платформы (rabota.by, Habr Career, LinkedIn).

---

## Фаза 0 — Manual feed (сейчас)

Файл `data/manual_events.json` — вы или агент добавляете события вручную.

Плюсы: стабильно, без блокировок, быстрый старт.

---

## Фаза 1 — Кандидаты на подключение

> Перед парсингом проверьте robots.txt и правила сайта. Не DDoS-ить источники.

### Стажировки / вакансии для juniors

| Источник | Тип | Комментарий |
|----------|-----|-------------|
| [rabota.by](https://rabota.by/stazhirovki) | Web / поиск | стажировки QA Trainee/Junior (**v0.3 live**) |
| [jobs.tut.by](https://jobs.tut.by) | поиск «стажировка» | фильтр по ключевым словам |
| [Habr Career](https://career.habr.com) | Web / поиск | QA remote intern/junior (**v0.4 live**) |
| [LinkedIn](https://linkedin.com) | ручной / email alerts | «internship Belarus remote» |
| Telegram-каналы HR/IT | RSS через tg или ручной | см. ниже |

### Митапы / конференции

| Источник | Тип |
|----------|-----|
| [IT Events BY (community)](https://t.me) | Telegram-каналы (искать вручную) |
| GDG Minsk, Python Belarus, QA communities | Telegram / Meetup |
| [Space / ПВТ events](https://park.by) | календари площадок |
| Habr Career / профильные IT-сообщества | RSS, анонсы |

### Telegram-каналы (активные — v0.1 manual feed)

| Организация | Telegram | Сайт событий |
|-------------|----------|--------------|
| **ASTON** | [@astonit](https://t.me/astonit) | [career.astondevs.ru](https://career.astondevs.ru/newsletter) |
| **Andersen** | [@andersen_people](https://t.me/andersen_people) | [people.andersenlab.com](https://people.andersenlab.com/meetups-with-andersen-recaps) |
| **IT-Academy** | [@it_academy_by](https://t.me/it_academy_by) | [it-academy.by/media/sobytiya](https://www.it-academy.by/media/sobytiya/) |
| **Minsk Python** | [@minsk_python](https://t.me/minsk_python), [@minsk_python_jobs](https://t.me/minsk_python_jobs) | [minskpython.github.io](https://minskpython.github.io/) |
| **Belarus: хочу в IT** | [@belarusitwant](https://t.me/belarusitwant) | — (v0.3: live RSS) |

> Для вакансий и стажировок: rabota.by, Habr Career, LinkedIn (email alerts). Telegram-каналы — для митапов и анонсов сообществ.

### Telegram-каналы (примеры направлений — уточнять актуальные)

- IT-новости Беларуси
- QA / Python / JS communities
- Каналы коворкингов и tech-hub

**MVP-подход:** один канал → ручное добавление в feed → потом автоматизация.

---

## Нормализация

Все источники приводятся к `Event`:

```json
{
  "id": "uuid",
  "type": "meetup | internship | conference",
  "title": "Python Meetup Minsk",
  "date": "2026-08-15",
  "date_end": null,
  "location": "Минск / online",
  "tags": ["python", "meetup"],
  "url": "https://...",
  "source": "manual_feed",
  "source_url": "https://...",
  "fetched_at": "2026-07-30T09:00:00+03:00"
}
```

---

## Теги для фильтра support-бота

- `meetup`, `conference`, `internship`, `junior`, `qa`, `python`, `js`, `ai`, `remote`, `minsk`, `online`
