@echo off
REM ================================================================================
REM  АНАЛІЗ TELEGRAM ЧАТІВ ЧЕРЕЗ ChatGPT + Playwright
REM ================================================================================
REM
REM  Подвійний клік на цей файл щоб запустити аналіз
REM
REM  Що робить скрипт:
REM    1. Запускає Chrome з remote debugging
REM    2. Відкриває чат ChatGPT
REM    3. Перевіряє підключення
REM    4. Запускає Python скрипт для аналізу
REM
REM  Вам потрібно:
REM    - Бути авторизованим в ChatGPT
REM    - Ввести посилання на Telegram чати
REM
REM  Результати:
REM    output/chat_analysis_data.txt - зібрані дані
REM    output/chat_descriptions.txt - готові описи
REM
REM  Документація: QUICK_START.md, PLAYWRIGHT_README.md
REM
REM ================================================================================

chcp 65001 >nul
cls

echo ================================================================================
echo                    АНАЛІЗ TELEGRAM ЧАТІВ ЧЕРЕЗ ChatGPT
echo ================================================================================
echo.
echo Цей скрипт автоматично:
echo   1. Запустить Chrome з remote debugging
echo   2. Відкриє потрібний чат ChatGPT
echo   3. Запустить Python скрипт для аналізу
echo.
echo ================================================================================
echo.

REM Перевірка віртуального середовища
if not exist "venv\Scripts\python.exe" (
    echo ❌ ПОМИЛКА: Віртуальне середовище не знайдено!
    echo 💡 Запустіть спочатку: python -m venv venv
    echo 💡 Потім: venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

echo ✅ Віртуальне середовище знайдено
echo.

REM Перевірка чи встановлено Playwright
venv\Scripts\python -c "import playwright" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Playwright не встановлено. Встановлюю...
    venv\Scripts\pip install playwright
    venv\Scripts\playwright install chromium
    echo ✅ Playwright встановлено
    echo.
)

echo ================================================================================
echo КРОК 1: Запуск Chrome
echo ================================================================================
echo.
echo 🌐 Запускаю Chrome з remote debugging на порту 9222...
echo.

REM Запускаємо Chrome в фоні
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-playwright-profile" "https://chatgpt.com/c/6937098c-d498-832a-8921-8e543d15ff2f"

echo ✅ Chrome запущено
echo.
echo 💡 ВАЖЛИВО:
echo    - Перевірте що ви АВТОРИЗОВАНІ в ChatGPT
echo    - Чат має бути ВІДКРИТИЙ: https://chatgpt.com/c/6937098c-d498-832a-8921-8e543d15ff2f
echo.

REM Даємо час на запуск Chrome та авторизацію
echo ⏳ Чекаємо 10 секунд поки Chrome запуститься...
timeout /t 10 /nobreak >nul

echo.
echo ================================================================================
echo КРОК 2: Перевірка підключення
echo ================================================================================
echo.

REM Перевіряємо чи Chrome запущено на порту 9222
curl -s http://localhost:9222/json >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Chrome ще не готовий, чекаємо ще 5 секунд...
    timeout /t 5 /nobreak >nul
)

curl -s http://localhost:9222/json >nul 2>&1
if errorlevel 1 (
    echo ❌ Не можу підключитись до Chrome
    echo 💡 Перевірте що Chrome запущено і порт 9222 доступний
    echo.
    pause
    exit /b 1
)

echo ✅ Chrome готовий до роботи
echo.

echo ================================================================================
echo КРОК 3: Авторизація в ChatGPT
echo ================================================================================
echo.
echo 💡 Переконайтесь що ви авторизовані в ChatGPT!
echo.
echo Якщо ви вже авторизовані - натисніть Enter
echo Якщо НІ - авторизуйтесь в відкритому Chrome і потім натисніть Enter
echo.
pause

echo.
echo ================================================================================
echo КРОК 4: Запуск аналізу
echo ================================================================================
echo.

REM Запускаємо Python скрипт через віртуальне середовище
venv\Scripts\python analyze_chats_playwright.py

echo.
echo ================================================================================
echo ЗАВЕРШЕНО
echo ================================================================================
echo.
echo 📁 Результати збережено в папці output/
echo    - chat_analysis_data.txt (зібрані дані)
echo    - chat_descriptions.txt (готові описи)
echo.
echo 💡 Chrome залишається відкритим для наступних запусків
echo    Можете запустити RUN.bat ще раз без перезапуску Chrome
echo.
pause
