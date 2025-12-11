@echo off
REM Batch script to run AdsPower Discord Automation on Windows

echo ============================================================
echo   AdsPower Discord Automation RPA
echo ============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

REM Check if config exists
if not exist "config.yaml" (
    echo ERROR: config.yaml not found
    echo Please create configuration file from config.example.yaml
    echo.
    echo Run: copy config.example.yaml config.yaml
    echo Then edit config.yaml with your settings
    pause
    exit /b 1
)

REM Run the automation
python main.py

pause

