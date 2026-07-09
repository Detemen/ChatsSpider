@echo off
chcp 65001 >nul 2>&1
cls

echo ==============================================================================
echo   AUTO START - TelegramAnalysis v2.0
echo ==============================================================================
echo.

REM Check virtual environment
if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo [INFO] Creating virtual environment...
    python -m venv venv
    echo [OK] Virtual environment created
    echo.
    echo [INFO] Installing dependencies...
    venv\Scripts\python.exe -m pip install -q python-dotenv telethon playwright
    echo [OK] Dependencies installed
    echo.
)

REM Check if Chrome is already running on port 9222
echo [INFO] Checking Chrome on port 9222...
netstat -an | findstr ":9222" >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Chrome is already running on port 9222
) else (
    echo [INFO] Starting Chrome with remote debugging...
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-playwright-profile" "https://chatgpt.com"
    echo [INFO] Waiting 5 seconds for Chrome to start...
    timeout /t 5 /nobreak >nul
    echo [OK] Chrome started
)

echo.
echo ==============================================================================
echo   STARTING CHAT ANALYSIS
echo ==============================================================================
echo.
echo [!] Please login to ChatGPT in Chrome if not already logged in
echo [!] System will process 1344 chats (~9 hours)
echo [!] Rate limit: 150 chats/hour
echo [!] Logs: state\chats_spider.log
echo [!] Press Ctrl+C to stop (progress will be saved)
echo.
echo [INFO] Starting in 3 seconds...
timeout /t 3 /nobreak >nul

echo.
echo [START] Running analysis...
echo.

REM Run Python script in AUTO mode
venv\Scripts\python.exe analyze_chats_playwright.py --auto

echo.
echo ==============================================================================
echo   COMPLETED
echo ==============================================================================
echo.
echo [INFO] Check results:
echo    - output\validated_chats.txt
echo    - output\rejected_chats.txt
echo    - state\chats_spider.log
echo.
echo [INFO] View statistics: venv\Scripts\python.exe utils\inspect_state.py
echo.
echo.
echo Press any key to close this window...
pause >nul
