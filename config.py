"""
Configuration for Team Performance Dashboard

Set these environment variables before running (or use .env file):
- JIRA_URL: Your Jira Cloud instance (e.g., https://atlasergonomics.atlassian.net)
- JIRA_EMAIL: Your Atlassian account email
- JIRA_API_TOKEN: API token from https://id.atlassian.com/manage-profile/security/api-tokens
- SLACK_WEBHOOK_URL: Incoming webhook URL for your private channel
- GITHUB_TOKEN: (Optional) Personal access token from https://github.com/settings/tokens
"""

import os
from pathlib import Path

# Load .env file if it exists
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

# Jira Configuration
JIRA_URL = os.getenv("JIRA_URL", "https://atlasergonomics.atlassian.net")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "AEB")

# Jira Workflow Statuses (in order)
WORKFLOW_STATUSES = [
    "To Do",
    "Re-opened",
    "In Progress",
    "Ready for Deployment",
    "Dev Checks",
    "Ready for Testing",
    "Ready for Production",
    "Done"
]

# Status that indicates a ticket was reopened
REOPEN_STATUS = "Re-opened"

# Team members (display name in Jira -> friendly name)
TEAM_MEMBERS = {
    "Deep": "Deep",
    "Meet": "Meet",
    "Devansh": "Devansh",
    "Vipin": "Vipin",
    "Mike Perry": "Mike Perry",
}

# Slack Configuration
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# Slack Bot Configuration (for reading standup messages)
# Bot token starts with xoxb- and needs channels:history and users:read scopes
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_STANDUP_CHANNEL = os.getenv("SLACK_STANDUP_CHANNEL", "ongoing-sprint-work")
SLACK_STANDUP_CHANNEL_ID = os.getenv("SLACK_STANDUP_CHANNEL_ID", "")  # Channel ID (starts with C)
SLACK_VIPIN_CHANNEL_ID = os.getenv("SLACK_VIPIN_CHANNEL_ID", "")  # Vipin's update channel

# GitHub Configuration (Optional - set GITHUB_ENABLED=true to enable)
GITHUB_ENABLED = os.getenv("GITHUB_ENABLED", "false").lower() == "true"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_ORG = os.getenv("GITHUB_ORG", "voidsstr")
GITHUB_REPO = os.getenv("GITHUB_REPO", "AtlasErgoBackend")

# Metrics Configuration
STALE_THRESHOLD_DAYS = int(os.getenv("STALE_THRESHOLD_DAYS", "3"))
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "30"))

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", "team_metrics.db")

# Dashboard
DASHBOARD_HOST = os.getenv("DASHBOARD_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "5000"))
