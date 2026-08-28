@echo off
title CookieRun Classic Bot - Web Dashboard
cd /d "%~dp0\src"
echo ========================================================
echo   CookieRun Classic Bot - Starting Web Dashboard...
echo ========================================================
python run_web.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Cannot run Python or required packages are missing!
    echo Please run 'INSTALL.bat' first or make sure Python is installed and added to PATH.
    echo.
    pause
)
