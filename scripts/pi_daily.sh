#!/bin/bash
# Daily AI Digest - Runs Monday through Thursday at 7:00 AM
# Pulls latest code from GitHub, then runs daily analysis

set -e

PROJECT_DIR="$HOME/jira-dashboard"
LOG_DIR="$PROJECT_DIR/logs"
LOGFILE="$LOG_DIR/daily_$(date +%Y%m%d).log"

# Create logs directory if needed
mkdir -p "$LOG_DIR"

echo "[$(date)] Starting daily digest..." >> "$LOGFILE"

# Pull latest code from GitHub
cd "$PROJECT_DIR"
echo "[$(date)] Pulling latest code from GitHub..." >> "$LOGFILE"
git pull origin master >> "$LOGFILE" 2>&1

# Run the daily AI digest
echo "[$(date)] Running daily-ai..." >> "$LOGFILE"
python3 main.py daily-ai >> "$LOGFILE" 2>&1

echo "[$(date)] Daily digest complete." >> "$LOGFILE"
