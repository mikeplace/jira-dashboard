@echo off
REM Daily job runner for Windows/Jenkins
REM Schedule this script to run at 7:00 AM daily
REM
REM Usage:
REM   run_daily.bat          - Run with AI analysis (requires Claude Code)
REM   run_daily.bat --no-ai  - Run without AI analysis

cd /d "%~dp0"

REM Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Check for --no-ai flag
if "%1"=="--no-ai" (
    echo Running daily job WITHOUT AI analysis...
    python main.py daily
) else (
    echo Running daily job WITH AI analysis...
    python main.py daily-ai
)

REM Exit with python's exit code
exit /b %ERRORLEVEL%
