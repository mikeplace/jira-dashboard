# Jira Team Performance Dashboard

## Overview
AI-powered team performance monitoring system that syncs Jira data, analyzes team performance with Claude, and sends daily/weekly digests to Slack.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Jira Cloud     │     │  Slack          │     │  GitHub         │
│  (Your project) │     │  (Webhooks+Bot) │     │  (This repo)    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────┬───────────┴───────────────────────┘
                     │
              ┌──────▼──────┐
              │ Raspberry Pi │  (or any Linux host)
              │ Claude Code  │
              │ Cron @ 6AM   │
              └──────────────┘
```

## Jira Workflow (8 statuses)
```
To Do → Re-opened → In Progress → Ready for Deployment → Dev Checks → Ready for Testing → Ready for Production → Done
```

## Key Files
- `main.py` - CLI entry point (sync, daily-ai, weekly-ai, etc.)
- `collector.py` - Jira API sync (uses `/rest/api/3/search/jql` POST)
- `metrics.py` - Velocity, reopen rates, time-in-status calculations
- `analysis.py` - Advanced analysis (ETA vs actual, backlog prediction, quality metrics)
- `slack_notifier.py` - Formats and sends Slack messages
- `slack_reader.py` - Reads standup messages from Slack channels
- `config.py` - Loads environment from `.env`

## Slack Messages
- Uses Slack mrkdwn: `*bold*`, `_italic_`, `:emoji_name:`
- Jira links: `<https://your-instance.atlassian.net/browse/PROJ-123|PROJ-123>`

## Raspberry Pi Setup
- **Project**: `~/jira-dashboard`
- **Virtual env**: `~/jira-dashboard/venv`
- **Cron jobs**:
  - Mon-Thu 6:00 AM: `scripts/pi_daily.sh`
  - Friday 6:00 AM: `scripts/pi_weekly.sh`
- Scripts auto-pull from GitHub before each run

## Environment Variables (in .env)
```
JIRA_URL=https://your-instance.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=<token>
JIRA_PROJECT_KEY=PROJ
SLACK_WEBHOOK_URL=<webhook>
SLACK_BOT_TOKEN=<bot-token>
SLACK_STANDUP_CHANNEL_ID=<channel-id>
```

## Key Commands
```bash
# On Mac (testing)
python3 main.py sync           # Sync Jira data
python3 main.py daily-ai       # Run daily digest with AI
python3 main.py weekly-ai      # Run weekly summary with AI
python3 main.py report         # Generate text report for Claude
python3 main.py test-standup   # Test standup parsing

# On Raspberry Pi
cd ~/jira-dashboard && source venv/bin/activate
python3 main.py daily-ai
```

## Metrics Tracked
- **Velocity**: Tickets reaching "Ready for Production" (not Done)
- **Reopen Rate**: Per developer, tickets moved to "Re-opened"
- **Time in Status**: Average hours in each workflow status
- **Stale Tickets**: No updates > 3 days (categorized as "new" vs "ongoing")
- **Quality Metrics**: Bugs found in testing per developer
- **ETA vs Actual**: Compares stated ETAs in standups with actual delivery
- **Backlog Prediction**: Days to clear based on velocity

## Standup Analysis
Reads from configured Slack channels and compares what team members say in standups vs actual Jira movement to flag discrepancies.

## Important Notes
- "Highest" priority tickets = Expedite tickets
- "Next-Release" label = Priority for upcoming release
- Configure team members in `config.py` to match your Jira display names
- Repo is public but `.env` with credentials is gitignored
