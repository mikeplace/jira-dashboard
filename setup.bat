@echo off
REM Initial setup script for Windows

echo ========================================
echo Team Performance Dashboard Setup
echo ========================================
echo.

cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

echo Creating virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo ========================================
echo Setup complete!
echo ========================================
echo.
echo Next steps:
echo.
echo 1. Create environment file:
echo    Copy .env.example to .env and fill in your credentials
echo.
echo 2. Test the connection:
echo    python main.py sync
echo.
echo 3. Test Slack:
echo    python main.py test-slack
echo.
echo 4. Start dashboard:
echo    start_dashboard.bat
echo.
echo 5. Schedule daily job:
echo    Add run_daily.bat to Windows Task Scheduler at 7:00 AM
echo.
pause
