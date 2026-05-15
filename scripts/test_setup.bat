@echo off
REM Test script to verify the Jira Dashboard setup is working
REM Run this before setting up the scheduler

setlocal

REM Set the project directory (update this path)
set PROJECT_DIR=C:\jira-dashboard

echo ============================================
echo Jira Dashboard - Setup Verification
echo ============================================
echo.

cd /d "%PROJECT_DIR%"

echo [1/5] Checking Python installation...
python --version >nul 2>&1
if %errorLevel% equ 0 (
    echo   [OK] Python is installed
    python --version
) else (
    echo   [ERROR] Python is not installed or not in PATH
    goto :error
)
echo.

echo [2/5] Checking Claude Code installation...
claude --version >nul 2>&1
if %errorLevel% equ 0 (
    echo   [OK] Claude Code is installed
    claude --version
) else (
    echo   [ERROR] Claude Code is not installed
    echo   Install with: npm install -g @anthropic-ai/claude-code
    goto :error
)
echo.

echo [3/5] Checking .env file...
if exist "%PROJECT_DIR%\.env" (
    echo   [OK] .env file exists
) else (
    echo   [ERROR] .env file not found in %PROJECT_DIR%
    goto :error
)
echo.

echo [4/5] Testing Jira connection (sync)...
python main.py sync
if %errorLevel% equ 0 (
    echo   [OK] Jira sync successful
) else (
    echo   [WARNING] Jira sync had issues - check credentials
)
echo.

echo [5/5] Testing Claude Code authentication...
echo   Running: claude -p "Say OK if you can hear me" --print
claude -p "Say OK if you can hear me" --print
if %errorLevel% equ 0 (
    echo.
    echo   [OK] Claude Code is authenticated and working
) else (
    echo   [ERROR] Claude Code authentication failed
    echo   Run: claude setup-token
    goto :error
)
echo.

echo ============================================
echo All checks passed! Ready to set up scheduler.
echo ============================================
echo.
echo Next step: Run setup_scheduler.bat as Administrator
echo.
pause
exit /b 0

:error
echo.
echo ============================================
echo Setup verification FAILED
echo Please fix the errors above before proceeding.
echo ============================================
pause
exit /b 1
