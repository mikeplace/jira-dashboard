@echo off
REM Daily Digest - Runs Monday through Thursday at 7:00 AM
REM Syncs Jira data and sends basic digest to Slack

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

REM Run sync and basic daily digest (no AI - Server 2016 compatible)
echo [%date% %time%] Starting daily digest... >> logs\daily_%LOGDATE%.log
python main.py daily >> logs\daily_%LOGDATE%.log 2>&1
echo [%date% %time%] Daily digest complete. >> logs\daily_%LOGDATE%.log

endlocal
