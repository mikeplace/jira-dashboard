@echo off
REM Setup Windows Task Scheduler for Jira Dashboard
REM Run this script as Administrator

setlocal

REM Set the project directory (update this path)
set PROJECT_DIR=C:\jira-dashboard
set SCRIPTS_DIR=%PROJECT_DIR%\scripts

echo ============================================
echo Jira Dashboard - Task Scheduler Setup
echo ============================================
echo.

REM Check for admin privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ERROR: This script requires Administrator privileges.
    echo Please right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo Project Directory: %PROJECT_DIR%
echo.

REM Create the daily digest task (Monday-Thursday at 7:00 AM)
echo Creating Daily Digest task (Mon-Thu 7:00 AM)...
schtasks /create /tn "Jira Dashboard - Daily Digest" ^
    /tr "\"%SCRIPTS_DIR%\daily_digest.bat\"" ^
    /sc weekly /d MON,TUE,WED,THU ^
    /st 07:00 ^
    /ru SYSTEM ^
    /rl HIGHEST ^
    /f

if %errorLevel% equ 0 (
    echo   [OK] Daily Digest task created successfully
) else (
    echo   [ERROR] Failed to create Daily Digest task
)

echo.

REM Create the weekly summary task (Friday at 7:00 AM)
echo Creating Weekly Summary task (Fri 7:00 AM)...
schtasks /create /tn "Jira Dashboard - Weekly Summary" ^
    /tr "\"%SCRIPTS_DIR%\weekly_summary.bat\"" ^
    /sc weekly /d FRI ^
    /st 07:00 ^
    /ru SYSTEM ^
    /rl HIGHEST ^
    /f

if %errorLevel% equ 0 (
    echo   [OK] Weekly Summary task created successfully
) else (
    echo   [ERROR] Failed to create Weekly Summary task
)

echo.
echo ============================================
echo Setup Complete!
echo ============================================
echo.
echo Tasks created:
echo   1. "Jira Dashboard - Daily Digest" - Mon-Thu at 7:00 AM
echo   2. "Jira Dashboard - Weekly Summary" - Fri at 7:00 AM
echo.
echo To verify, open Task Scheduler and look for "Jira Dashboard" tasks.
echo.
echo IMPORTANT: Before running, make sure you have:
echo   1. Installed Python and added to PATH
echo   2. Installed Claude Code: npm install -g @anthropic-ai/claude-code
echo   3. Run "claude setup-token" to authenticate
echo   4. Copied the project to %PROJECT_DIR%
echo   5. Updated the .env file with your credentials
echo.
pause
