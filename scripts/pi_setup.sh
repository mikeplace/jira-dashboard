#!/bin/bash
# Raspberry Pi Setup Script for Jira Dashboard
# Run this once to set up the Pi

set -e

echo "============================================"
echo "Jira Dashboard - Raspberry Pi Setup"
echo "============================================"
echo

# Update system
echo "[1/6] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install Python and pip
echo "[2/6] Installing Python..."
sudo apt install -y python3 python3-pip python3-venv

# Install Node.js (for Claude Code)
echo "[3/6] Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install Claude Code
echo "[4/6] Installing Claude Code..."
sudo npm install -g @anthropic-ai/claude-code

# Clone the repo
echo "[5/6] Cloning jira-dashboard repo..."
cd ~
git clone https://github.com/mikeplace/jira-dashboard.git
cd jira-dashboard

# Install Python dependencies
echo "[6/6] Installing Python dependencies..."
pip3 install -r requirements.txt

echo
echo "============================================"
echo "Setup complete!"
echo "============================================"
echo
echo "Next steps:"
echo "  1. Create .env file with your credentials:"
echo "     cp .env.example .env"
echo "     nano .env"
echo
echo "  2. Authenticate Claude Code:"
echo "     claude setup-token"
echo
echo "  3. Test the setup:"
echo "     python3 main.py sync"
echo "     python3 main.py daily-ai"
echo
echo "  4. Set up cron jobs (run: crontab -e):"
echo "     0 7 * * 1-4 $HOME/jira-dashboard/scripts/pi_daily.sh"
echo "     0 7 * * 5 $HOME/jira-dashboard/scripts/pi_weekly.sh"
echo
