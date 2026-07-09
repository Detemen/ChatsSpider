# Analyze Chats - Аналіз Telegram чатів з ChatGPT

Скрипт для автоматичної генерації детальних описів Telegram чатів.

## Як це працює

1. **Telethon збирає дані:**
   - Назва чату
   - Опис (about)
   - Кількість учасників
   - Закріплене повідомлення
   - Список адміністраторів
   - Пов'язаний канал (якщо є)

2. **Зберігає в файл** `output/chat_analysis_data.txt`

3. **Selenium відкриває ChatGPT** (ваш авторизований браузер)

4. **Автоматично відправляє промпти** для кожного чату

5. **Зберігає результат** в `output/chat_descriptions.txt`

## Передумови

### 1. Chrome WebDriver

Selenium потребує ChromeDriver. Встановіть один зі способів:

**Спосіб 1: Автоматичне встановлення (рекомендовано)**
Сучасні версії Selenium автоматично завантажують ChromeDriver.

**Спосіб 2: Ручне встановлення**
```bash
# Завантажте ChromeDriver:
# https://chromedriver.chromium.org/downloads

# Додайте в PATH або помістіть в папку проекту
```

### 2. Авторизація в ChatGPT

Перед запуском скрипту:
1. Відкрийте Chrome
2. Перейдіть на https://chat.openai.com/
3. Авторизуйтеся
4. Закрийте браузер

Selenium використає ваш профіль Chrome з авторизацією.

## Запуск

### Крок 1: Підготовка чатів

Підготуйте посилання на чати:
```
https://t.me/DIY_Serbia
https://t.me/eda_rs
https://t.me/augmoscow
```

### Крок 2: Запуск скрипту

```bash
cd F:\PY\ChatsSpider
venv\Scripts\python analyze_chats.py
```

### Крок 3: Введення даних

```
Введіть посилання на Telegram чати (по одному на рядок):
Після останнього посилання натисніть Enter двічі

https://t.me/DIY_Serbia
https://t.me/eda_rs
https://t.me/augmoscow
[Enter]
[Enter]
```

### Крок 4: Збір даних через Telethon

Скрипт автоматично:
- Підключиться до Telegram
- Зібере всю інформацію про чати
- Збереже в файл

### Крок 5: Генерація описів

```
Продовжити? (y/n): y
```

Відкриється браузер Chrome з ChatGPT. Скрипт автоматично:
- Відправить промпт для кожного чату
- Почекає на відповідь
- Збере результати

### Крок 6: Результат

Фінальний файл `output/chat_descriptions.txt`:
```
Чат про DIY проекти та саморобки в Сербії, обмін досвідом між майстрами
(https://t.me/DIY_Serbia) (@admin_username)

Кулінарний чат для любителів сербської кухні, рецепти та поради
(https://t.me/eda_rs) (@chef_admin)

...
```

## Налаштування

### Використання власного профілю Chrome

Якщо хочете використати конкретний профіль Chrome:

Відредагуйте `analyze_chats.py` (рядок 33):
```python
CHROME_PROFILE_PATH = "C:/Users/YourName/AppData/Local/Google/Chrome/User Data"
```

### Безголовий режим (headless)

Для роботи без відкриття вікна браузера:

Розкоментуйте в `analyze_chats.py` (рядок 172):
```python
chrome_options.add_argument("--headless")
```

## Формат виводу

### Правильні приклади:

✅ "Фриланс чат для дизайнерів та SMM-спеціалістів (https://t.me/chat) (@admin)"

✅ "Чат по арбітражу трафіку, кейси, офери, поради (https://t.me/chat) (@admin)"

✅ "Спільнота розробників на Python, обговорення бібліотек та проектів (https://t.me/chat) (@admin)"

### Неправильні приклади:

❌ "Маркетинг чат"

❌ "Фриланс"

❌ "Чат про роботу"

## Troubleshooting

### "SessionNotFound" або "ChromeDriver not found"

```bash
pip install webdriver-manager
```

Додайте в код:
```python
from webdriver_manager.chrome import ChromeDriverManager
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
```

### ChatGPT не авторизований

1. Вручну відкрийте Chrome
2. Авторизуйтеся на chat.openai.com
3. НЕ закривайте профіль
4. Запустіть скрипт знову

### Селектори не працюють

ChatGPT може змінити дизайн. Оновіть селектори в коді:
- Рядок 196: `textarea` - поле вводу
- Рядок 215: `[data-message-author-role='assistant']` - відповіді

### FloodWait від Telegram

Це нормально. Скрипт автоматично чекає.

## Структура файлів

```
output/
├── chat_analysis_data.txt      # Зібрані дані (для перегляду)
└── chat_descriptions.txt       # Фінальні описи (результат)
```

## Обмеження

- **ChatGPT Free** - може бути повільніше
- **Rate Limits** - ChatGPT може обмежувати кількість запитів
- **Приватні чати** - потрібен доступ до чату через ваш акаунт

## Поради

1. **Невеликі партії** - обробляйте по 3-5 чатів за раз
2. **Перевіряйте дані** - переглядайте `chat_analysis_data.txt` перед генерацією
3. **Редагуйте промпт** - змініть промпт в коді для кращих результатів
4. **Зберігайте результати** - файли не перезаписуються автоматично

## Приклад використання

```bash
# Запуск
python analyze_chats.py

# Введення
https://t.me/pythondevs
https://t.me/webdesign_chat
https://t.me/crypto_trading

[Enter x2]

# Результат через 2-3 хвилини:
# output/chat_descriptions.txt
```

## Ліцензія

MIT
