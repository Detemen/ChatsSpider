# Telegram Spider - ChatsSpider

Мульти-аккаунтний парсер Telegram каналів та чатів на базі Telethon.

## 🚀 НОВИНКА: Аналіз чатів через ChatGPT + Playwright

**Найпростіший спосіб - 1 клік:**
```
Подвійний клік на RUN.bat
```

Автоматично запустить Chrome, ChatGPT і почне аналіз чатів!

📖 Детальна інструкція: [QUICK_START.md](QUICK_START.md) | [PLAYWRIGHT_README.md](PLAYWRIGHT_README.md)

---

## Можливості

### Парсер каналів (spider_telethon.py)
- ✅ Збір каналів-донорів та схожих каналів через API рекомендацій
- ✅ Пошук публічних обговорень (linked chats)
- ✅ Робота через проксі (SOCKS5/HTTP)
- ✅ Мульти-акаунтна підтримка
- ✅ SQLite база даних
- ✅ Кольоровий статус в реальному часі

### Аналіз чатів через ChatGPT (analyze_chats_playwright.py)
- ✅ Автоматичний збір інформації про чати (Telethon)
- ✅ Генерація описів через ChatGPT (Playwright)
- ✅ Робота в одному чаті ChatGPT (не створює нові вкладки)
- ✅ Підключення до запущеного Chrome (не потрібна повторна авторизація)

## Встановлення

```bash
# Створити віртуальне середовище
python -m venv venv

# Активувати
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Встановити залежності
pip install -r requirements.txt
```

## Налаштування

### 1. API ключі Telegram

Створіть файл `.env`:

```env
API_ID=ваш_api_id
API_HASH=ваш_api_hash
```

Або використовуйте `config_accounts.json`:

```json
{
  "default": {
    "api_id": "ваш_api_id",
    "api_hash": "ваш_api_hash"
  }
}
```

### 2. Session файли

Розмістіть `.session` файли в папці `accs/`

### 3. Канали-донори (опціонально)

Створіть `channelsdb.txt` зі списком каналів:

```
https://t.me/channel1
https://t.me/channel2
@channel3
```

### 4. Проксі (опціонально)

Створіть `proxy.txt`:

```
ip:port
ip:port:user:pass
socks5://ip:port
```

## Параметри

Змініть параметри в `spider_telethon.py` (рядки 48-51):

```python
DELAY_MIN, DELAY_MAX = 0.8, 2.0           # Затримка між запитами (секунди)
PASS_PAUSE_MIN, PASS_PAUSE_MAX = 6, 10    # Пауза між проходами БД (секунди)
STATUS_REFRESH_SEC = 2.0                   # Оновлення статусу (секунди)
```

## Запуск

```bash
# З віртуальним середовищем
venv\Scripts\python spider_telethon.py

# Без віртуального середовища
python spider_telethon.py
```

## Фільтрація та експорт

Використовуйте `filter_database.py` для роботи з зібраними даними:

```bash
python filter_database.py
```

Меню опцій:
1. Показати статистику
2. Шукати канали
3. Шукати чати
4. Експорт всіх каналів
5. Експорт всіх чатів
6. Експорт з фільтром
7-9. Детальний експорт

### Швидкий експорт

Експортовані дані зберігаються в `output/`:
- `all_channels.txt` - всі канали (список URL)
- `all_chats.txt` - всі чати (список URL)

## Структура проекту

```
ChatsSpider/
├── accs/                      # Session файли
├── output/                    # Експортовані дані та БД
│   ├── spider.db             # SQLite база
│   ├── all_channels.txt      # Експорт каналів
│   └── all_chats.txt         # Експорт чатів
├── spider_telethon.py        # Основний скрипт
├── filter_database.py        # Фільтрація та експорт
├── database.py               # Робота з SQLite
├── channelsdb.txt            # Стартові канали
├── proxy.txt                 # Проксі (опціонально)
├── .env                      # API ключі
└── requirements.txt          # Залежності
```

## База даних

SQLite база `output/spider.db` містить дві таблиці:

### channels
- username (унікальний)
- title
- about (опис)
- first_seen_ts
- last_seen_ts
- source_session

### chats
- username (унікальний)
- title
- about (опис)
- channel_username (з якого каналу)
- first_seen_ts
- last_seen_ts
- source_session

## Troubleshooting

### "No module named 'socks'"
```bash
pip install pysocks
```

### "Сессия не авторизована"
Session файли застарілі або невалідні. Потрібно створити нові через офіційний Telegram клієнт або скрипт авторизації.

### FloodWait помилки
Це нормально - Telegram обмежує кількість запитів. Скрипт автоматично чекає потрібний час.

## Ліцензія

MIT
