@echo off
title Push SmartShelf to GitHub
echo ========================================================
echo   Push SmartShelf to GitHub Repository
echo   https://github.com/saran-assr/library_management_system
echo ========================================================
echo.

cd /d "%~dp0"
".venv\Scripts\python.exe" push_to_github.py
pause
