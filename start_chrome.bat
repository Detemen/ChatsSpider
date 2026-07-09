@echo off
echo ========================================
echo  Запуск Chrome для Playwright
echo ========================================
echo.
echo Chrome запускається з параметрами:
echo   - Remote debugging на порту 9222
echo   - Окремий профіль для Playwright
echo.
echo Після запуску:
echo   1. Перейдіть на https://chatgpt.com/c/6937098c-d498-832a-8921-8e543d15ff2f
echo   2. Авторизуйтесь (якщо потрібно)
echo   3. Запустіть скрипт: python analyze_chats_playwright.py
echo.
echo ========================================
echo.

"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-playwright-profile"

pause
