@echo off
title SmartShelf — Intelligent Library Management System
echo ========================================================
echo   SmartShelf — Intelligent Library Management System
echo ========================================================
echo.

cd /d "%~dp0"

IF NOT EXIST ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Please run: python -m venv .venv ^&^& .\.venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

IF NOT EXIST "instance\library.db" (
    echo [INFO] Initializing and seeding demo database...
    ".venv\Scripts\python.exe" seed.py
)

echo [INFO] Starting SmartShelf server...
echo Access the application at: http://127.0.0.1:5000
echo Press Ctrl+C to stop the server.
echo.

".venv\Scripts\python.exe" wsgi.py
pause
