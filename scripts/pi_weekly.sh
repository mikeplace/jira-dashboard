#!/bin/bash
# Weekly AI Summary - Runs Friday at 7:00 AM
# Pulls latest code from GitHub, then runs weekly analysis

PROJECT_DIR="$HOME/jira-dashboard"
LOG_DIR="$PROJECT_DIR/logs"
LOGFILE="$LOG_DIR/weekly_$(date +%Y%m%d).log"

# Create logs directory if needed
mkdir -p "$LOG_DIR"

echo "[$(date)] Starting weekly summary..." >> "$LOGFILE"

# Pull latest code from GitHub
cd "$PROJECT_DIR"
echo "[$(date)] Pulling latest code from GitHub..." >> "$LOGFILE"
git pull origin master >> "$LOGFILE" 2>&1

# Activate virtual environment and run the weekly AI summary
echo "[$(date)] Running weekly-ai..." >> "$LOGFILE"
source "$PROJECT_DIR/venv/bin/activate"
python3 main.py weekly-ai >> "$LOGFILE" 2>&1

echo "[$(date)] Weekly summary complete." >> "$LOGFILE"
