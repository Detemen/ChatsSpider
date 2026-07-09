@echo off
chcp 65001 >nul
cls

echo.
echo ================================================================================
echo   AUTOMATIC LAUNCH - TELEGRAM CHAT ANALYSIS
echo ================================================================================
echo.

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found!
    echo Please create it first: python -m venv venv
    echo.
    pause
    exit /b 1
)

echo Starting analysis...
echo.

venv\Scripts\python.exe START.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Script failed with code %ERRORLEVEL%
    echo.
)

echo.
echo ================================================================================
echo   COMPLETED
echo ================================================================================
echo.
pause
