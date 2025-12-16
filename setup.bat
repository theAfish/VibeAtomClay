@echo off
echo Starting VibeAtomClay Setup...

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in your PATH.
    echo Please install Python 3.8 or higher from https://www.python.org/
    pause
    exit /b 1
)

REM Run the Python setup script
python setup_dev.py

if %errorlevel% neq 0 (
    echo Setup failed with error code %errorlevel%
    pause
    exit /b %errorlevel%
)

echo.
echo Setup finished successfully!
pause
