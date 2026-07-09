@echo off
chcp 65001 >nul
echo ================================================================================
echo   ЗАПУСК TelegramAnalysis v2.0
echo ================================================================================
echo.

REM Перевірка віртуального середовища
if not exist "venv\Scripts\python.exe" (
    echo ❌ Віртуальне середовище не знайдено!
    echo 💡 Створіть його командою: python -m venv venv
    pause
    exit /b 1
)

echo 📦 Використовую віртуальне середовище: venv\Scripts\python.exe
echo.

REM Запуск скрипта
echo 🚀 Запуск analyze_chats_playwright.py --auto
echo.
venv\Scripts\python.exe analyze_chats_playwright.py --auto

echo.
echo ================================================================================
echo   ЗАВЕРШЕНО
echo ================================================================================
pause
