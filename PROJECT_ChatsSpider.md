# ChatsSpider

**Шлях:** `/Users/artemcvetkov/Projects/ChatsSpider`
**Останнє оновлення:** 06.06.2026
**Статус:** активний

## Призначення

Багатоакаунтний Telegram-спайдер: автоматично обходить публічні канали та збирає пов'язані чати-обговорення через Telethon API, зберігає в SQLite. Окремий pipeline генерує текстові описи зібраних чатів через ChatGPT (Playwright CDP), класифікує по 10 тематичних категоріях з ціноутворенням — для перепродажу рекламних розміщень (проект CommyX).

## Поточний стан

- ✅ Spider задеплоєний на сервері `2.26.125.134` у Docker-контейнері `chatsspider`
- ✅ Telegram моніторинг-бот (`chatsspider-bot`) запущений, сповіщення про зупинку сесії активні
- ✅ systemd-сервіс `chatsspider.service` — автозапуск при reboot
- ✅ 12 багів виправлено (безпека, OOM, race condition, resource leaks)
- ✅ 27/27 backtests пройшли
- ⏸ ChatGPT description pipeline (`generate_descriptions_only.py`) — не запущений на сервері (потребує Chrome з CDP)
- ⏸ Класифікація по категоріях підключена тільки в боті (не в spider при збереженні в БД)

## Ключові файли

- [spider_telethon.py](spider_telethon.py) — головний async crawler, нескінченний цикл по каналах
- [database.py](database.py) — SQLite wrapper, UPSERT з COALESCE, WAL-журнал
- [telegram_bot.py](telegram_bot.py) — aiogram 3.x бот: статистика, останні канали/чати, категорії, алерти
- [generate_descriptions_only.py](generate_descriptions_only.py) — Playwright CDP → ChatGPT → описи чатів
- [analyze_chats.py](analyze_chats.py) — старіший Selenium-варіант аналізу
- [filter_active_chats.py](filter_active_chats.py) — фільтр за активністю (>15 повідомлень/день) + ChatGPT-теги
- [filter_database.py](filter_database.py) — інтерактивне CLI-меню для пошуку/експорту з БД
- [make_session.py](make_session.py) — створення .session файлів (пише в `accs/`)
- [TelegramAnalysis/categories_config.py](TelegramAnalysis/categories_config.py) — 10 категорій, ціноутворення, keyword-матчинг
- [Dockerfile](Dockerfile) / [Dockerfile.bot](Dockerfile.bot) — Docker образи spider і бота
- [docker-compose.yml](docker-compose.yml) — 2 сервіси: `spider` + `bot`
- [chatsspider.service](chatsspider.service) — systemd unit
- [test_fixes.py](test_fixes.py) — 27 backtests (синтаксис, DB, spider utils, безпека)
- [.env](.env) — API_ID, API_HASH, BOT_TOKEN, CHATGPT_CONVERSATION_URL

## База даних

Проект використовує **SQLite** (`output/spider.db`).

### Зведення

| Таблиця | Напрям | Роль у проекті |
|---------|--------|----------------|
| `channels` | READ+WRITE | Зібрані Telegram-канали-донори та рекомендовані |
| `chats` | READ+WRITE | Публічні чати-обговорення знайдені з каналів |

### Детальні схеми

#### `channels`

**Призначення:** Зберігає публічні Telegram-канали знайдені через GetChannelRecommendationsRequest та seed-список. Читається spider-воркерами для вибірки наступної хвилі обходу.
**Ключ:** `username` (UNIQUE)

| # | Колонка | Тип | Опис |
|---|---------|-----|------|
| 1 | `id` | INTEGER PK | Автоінкремент |
| 2 | `username` | TEXT UNIQUE | t.me/<name> без https:// |
| 3 | `title` | TEXT | Назва каналу (Channel.title) |
| 4 | `about` | TEXT | Опис каналу (ChannelFull.about) |
| 5 | `first_seen_ts` | INTEGER | Unix-timestamp першого запису |
| 6 | `last_seen_ts` | INTEGER | Unix-timestamp останнього оновлення |
| 7 | `source_session` | TEXT | Ім'я .session файлу який знайшов |

#### `chats`

**Призначення:** Публічні чати-обговорення (linked chats) знайдені через GetFullChannelRequest. Основний продукт спайдера — саме чати продаються/аналізуються.
**Ключ:** `username` (UNIQUE)

| # | Колонка | Тип | Опис |
|---|---------|-----|------|
| 1 | `id` | INTEGER PK | Автоінкремент |
| 2 | `username` | TEXT UNIQUE | t.me/<name> обговорення |
| 3 | `title` | TEXT | Назва чату |
| 4 | `about` | TEXT | Опис чату (використовується для класифікації) |
| 5 | `channel_username` | TEXT | Канал-донор з якого знайдено чат |
| 6 | `first_seen_ts` | INTEGER | Unix-timestamp першого запису |
| 7 | `last_seen_ts` | INTEGER | Unix-timestamp останнього оновлення |
| 8 | `source_session` | TEXT | Ім'я .session файлу |

## Акаунти

| Файл сесії | Ім'я | Username | Телефон | Де використовується |
|---|---|---|---|---|
| `accs/my_account.session` | Artem Agent | без username | +254 (Кенія) | Тільки локально |
| `accs/1my_account.session` | 𝐓𝐒 | @mt_offer | +380 (Україна) | **На сервері** |

## Сервер

- **Host:** `root@2.26.125.134` (Ubuntu 22.04 LTS)
- **Docker:** 29.5.3
- **Шлях проекту:** `/opt/chatsspider/`
- **Контейнери:** `chatsspider` (spider) + `chatsspider-bot` (бот)
- **systemd:** `chatsspider.service` (enabled, автозапуск)

## Налаштування spider (поточні на сервері)

```python
CONCURRENT_ACCOUNTS = 20      # реально 1 акаунт
DELAY_MIN, DELAY_MAX = 3.0, 6.0          # між каналами (обережний режим)
PASS_PAUSE_MIN, PASS_PAUSE_MAX = 60, 120  # між проходами
get_all_channel_usernames(limit=200)      # захист від OOM
```

Проксі: **не налаштовані** (прямий IP).

## Класифікація (`categories_config.py`)

10 категорій для продажу реклами (проект CommyX):

| Категорія | Ціна high/low | Відп. |
|---|---|---|
| Crypto и GameFi | $2.25/$1.25 | manager |
| Арбитраж трафика | $2.50/$1.25 | founder |
| Маркетинг/SMM | $2.25/$1.00 | founder |
| Дизайн и Графика | $2.25/$1.00 | manager |
| Маркет-плейсы | $2.25/$1.00 | founder |
| IT-сфера | $1.75/$1.00 | manager |
| Инвестирование и Акции | $2.00/$1.00 | founder |
| Фриланс/Самозанятые | $1.50/$0.80 | founder |
| Спорт | $1.50/$0.80 | founder |
| Экспаты | $1.00/$0.50 | manager |

Класифікація в боті — keyword-матчинг по `about` + `title` чату.
Класифікація **не підключена** до spider при збереженні в БД.

## Telegram-бот

- **Команди:** `/start`, `/stats`, `/channels`, `/chats`, `/categories`, `/stop`
- **Алерти:** якщо `MAX(last_seen_ts)` старіше 15 хв → надсилає сповіщення підписникам
- **Відновлення:** надсилає `✅` коли спайдер відновлює роботу
- **Підписники:** зберігаються у `output/subscribers.json`
- **Перевірка:** кожні 5 хвилин

## Останні рішення

- 06.06.2026 — Збільшено затримки до 3-6с/60-120с (Why: мінімізація ризику бану @mt_offer)
- 06.06.2026 — Деплой на сервер тільки з 1 акаунтом `@mt_offer` (Why: безпека, не плутати акаунти)
- 06.06.2026 — `except Exception` → `except BaseException` у finally (Why: CancelledError не є Exception в Python 3.8+, контейнер падав у loop)
- 06.06.2026 — `DB.conn.execute` → `DB.get_all_channel_usernames(limit=200)` (Why: OOM при великій БД + інкапсуляція)
- 06.06.2026 — Volume `accs/` без `:ro` (Why: Telethon потребує запис у .session SQLite)

## Відкриті питання / TODOs

- [ ] Підключити автокласифікацію в spider при збереженні в БД (зараз тільки в боті)
- [ ] Налаштувати проксі для @mt_offer (зараз прямий IP — ризик бану)
- [ ] ChatGPT description pipeline на сервері (потребує headless-рішення замість CDP)
- [ ] Додати `crawled_at` в БД для розумнішої черги обходу каналів

## Технічні деталі

- **SSH:** `ssh root@2.26.125.134` (ключ, без пароля)
- **Корисні команди сервера:**
  ```bash
  docker logs chatsspider -f          # логи spider
  docker logs chatsspider-bot -f      # логи бота
  systemctl restart chatsspider       # перезапуск
  ls /opt/chatsspider/output/         # БД і результати
  ```
- **BOT_TOKEN** — у `.env`, не публікувати
- **CHATGPT_CONVERSATION_URL** — у `.env`, зараз не використовується (pipeline не запущений)
