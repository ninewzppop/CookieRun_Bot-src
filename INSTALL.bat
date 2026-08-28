@echo off
title CookieRun Classic Bot - Installation
cd /d "%~dp0\src"
echo ========================================================
echo   CookieRun Classic Bot - Installing Dependencies...
echo ========================================================
echo.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
if %ERRORLEVEL% EQU 0 (
    echo ========================================================
    echo   [SUCCESS] Installation completed successfully!
    echo   You can now start the bot using 'START_BOT.bat'.
    echo ========================================================
) else (
    echo ========================================================
    echo   [ERROR] Installation failed. 
    echo   Please ensure Python 3.10+ is installed and 'Add to PATH' was checked.
    echo ========================================================
)
echo.
pause
