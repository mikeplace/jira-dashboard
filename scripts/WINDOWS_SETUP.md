# Windows Server Setup Guide

## Prerequisites

1. **Python 3.x** - Download from https://python.org
   - During install, check "Add Python to PATH"

2. **Node.js** - Download from https://nodejs.org
   - Required for Claude Code installation

3. **Claude Code** - Install via npm:
   ```
   npm install -g @anthropic-ai/claude-code
   ```

4. **Claude Subscription** - Required for `setup-token`

## Installation Steps

### 1. Copy Project Files

Copy the entire `jira-dashboard` folder to `C:\jira-dashboard` on your Windows server.

### 2. Install Python Dependencies

Open Command Prompt and run:
```
cd C:\jira-dashboard
pip install -r requirements.txt
```

### 3. Configure Environment

Edit `C:\jira-dashboard\.env` with your credentials:
- JIRA_EMAIL
- JIRA_API_TOKEN
- SLACK_WEBHOOK_URL
- SLACK_BOT_TOKEN
- SLACK_STANDUP_CHANNEL_ID
- SLACK_VIPIN_CHANNEL_ID

### 4. Authenticate Claude Code

Run this once to create a long-lived token:
```
claude setup-token
```

Follow the prompts to authenticate.

### 5. Test the Setup

Run the test script:
```
cd C:\jira-dashboard\scripts
test_setup.bat
```

### 6. Create Scheduled Tasks

Run as Administrator:
```
cd C:\jira-dashboard\scripts
setup_scheduler.bat
```

## Scheduled Tasks

| Task | Schedule | Command |
|------|----------|---------|
| Daily Digest | Mon-Thu 7:00 AM | `python main.py daily-ai` |
| Weekly Summary | Fri 7:00 AM | `python main.py weekly-ai` |

## Logs

Logs are saved to `C:\jira-dashboard\logs\`:
- `daily_YYYYMMDD.log`
- `weekly_YYYYMMDD.log`

## Manual Testing

Test daily digest:
```
cd C:\jira-dashboard
python main.py daily-ai
```

Test weekly summary:
```
cd C:\jira-dashboard
python main.py weekly-ai
```

## Troubleshooting

### Claude Code not authenticated
```
claude setup-token
```

### Python not found
Make sure Python is in your system PATH.

### Jira connection fails
Check your JIRA_EMAIL and JIRA_API_TOKEN in .env

### Slack messages not sending
Verify SLACK_WEBHOOK_URL in .env
