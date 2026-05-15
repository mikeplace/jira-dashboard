# Jira Team Performance Dashboard

## Overview
AI-powered team performance monitoring system for Michael Place (Delivery & Test Lead) that syncs Jira data, analyzes team performance with Claude, and sends daily/weekly digests to Slack.

## Team
- **Michael Place** - Delivery & Test Lead (you - the user)
- **Vipin** - Tester
- **Deep, Meet, Devansh** - Developers (India)
- **Mike Perry** - Tech Lead

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Jira Cloud     │     │  Slack          │     │  GitHub         │
│  (AEB project)  │     │  (Webhooks+Bot) │     │  (This repo)    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────┬───────────┴───────────────────────┘
                     │
              ┌──────▼──────┐
              │ Raspberry Pi │  (greenhousepi.local)
              │ Claude Code  │
              │ Cron @ 7AM   │
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
- Title format: "Michael's Daily Assessment" / "Michael's Weekly Assessment"
- Uses Slack mrkdwn: `*bold*`, `_italic_`, `:emoji_name:`
- Jira links: `<https://atlasergonomics.atlassian.net/browse/AEB-123|AEB-123>`

## Raspberry Pi Setup
- **Host**: `greenhousepi.local` (SSH: `mikeplace@greenhousepi.local`)
- **Project**: `~/jira-dashboard`
- **Virtual env**: `~/jira-dashboard/venv`
- **Cron jobs**:
  - Mon-Thu 7:00 AM: `scripts/pi_daily.sh`
  - Friday 7:00 AM: `scripts/pi_weekly.sh`
- Scripts auto-pull from GitHub before each run

## Environment Variables (in .env)
```
JIRA_URL=https://atlasergonomics.atlassian.net
JIRA_EMAIL=mikeplace@gmail.com
JIRA_API_TOKEN=<token>
JIRA_PROJECT_KEY=AEB
SLACK_WEBHOOK_URL=<webhook>
SLACK_BOT_TOKEN=<bot-token>
SLACK_STANDUP_CHANNEL_ID=C024AG56MCZ
SLACK_VIPIN_CHANNEL_ID=C0B3Y0PG398
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
Reads from two Slack channels:
- Main standup channel (C024AG56MCZ)
- Vipin's testing updates (C0B3Y0PG398)

Compares what devs say in standups vs actual Jira movement to flag discrepancies.

## Important Notes
- "Highest" priority tickets = Expedite tickets
- "Next-Release" label = Priority for upcoming release
- Michael Place appears in data as the lead - focus analysis on devs (Deep, Meet, Devansh) and tester (Vipin)
- Repo is public but `.env` with credentials is gitignored
