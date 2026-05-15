@echo off
REM Weekly Summary - Runs Friday at 7:00 AM
REM Syncs Jira data and sends weekly summary to Slack

setlocal

REM Set the project directory (update this path on your Windows server)
set PROJECT_DIR=C:\jira-dashboard

REM Create logs directory if it doesn't exist
if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"

REM Generate timestamp for log file
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set LOGDATE=%datetime:~0,8%

REM Change to project directory
cd /d "%PROJECT_DIR%"

REM Run sync and basic weekly summary (no AI - Server 2016 compatible)
echo [%date% %time%] Starting weekly summary... >> logs\weekly_%LOGDATE%.log
python main.py sync >> logs\weekly_%LOGDATE%.log 2>&1
python main.py weekly >> logs\weekly_%LOGDATE%.log 2>&1
echo [%date% %time%] Weekly summary complete. >> logs\weekly_%LOGDATE%.log

endlocal
