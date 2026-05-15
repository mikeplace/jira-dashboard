@echo off
REM Start the dashboard server on Windows
REM Run this to start the web dashboard

cd /d "%~dp0"

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

echo Starting Team Performance Dashboard...
echo Dashboard will be available at http://localhost:5000
echo Press Ctrl+C to stop

REM Run dashboard in production mode
python main.py dashboard --production
