@echo off
echo Starting Chrome with remote debugging...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-playwright-profile"
echo Chrome started!
echo.
echo Now open https://chatgpt.com and login
echo Then run: python analyze_chats_playwright.py --auto
pause
