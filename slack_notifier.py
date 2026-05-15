"""
Slack notification sender for daily team digest.
"""

import requests
import json
from datetime import datetime
import config
import metrics


def jira_link(ticket_key: str) -> str:
    """Generate a Slack-formatted clickable Jira link."""
    url = f"{config.JIRA_URL}/browse/{ticket_key}"
    return f"<{url}|{ticket_key}>"


def send_slack_message(blocks: list, text: str = "Daily Team Insights"):
    """Send a message to Slack using incoming webhook."""
    if not config.SLACK_WEBHOOK_URL:
        print("Slack webhook URL not configured. Skipping notification.")
        return False

    payload = {
        "text": text,
        "blocks": blocks
    }

    response = requests.post(
        config.SLACK_WEBHOOK_URL,
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"}
    )

    if response.status_code == 200:
        print("Slack message sent successfully")
        return True
    else:
        print(f"Failed to send Slack message: {response.status_code} - {response.text}")
        return False


def format_daily_digest() -> list:
    """Format the daily digest as Slack blocks."""
    data = metrics.get_daily_digest_data()
    blocks = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"Daily Team Insights - {data['date']}"
        }
    })

    blocks.append({"type": "divider"})

    # Reopened Yesterday Section
    reopened = data["reopened_yesterday"]
    if reopened:
        reopened_text = f"*Reopened Yesterday ({len(reopened)})*\n"
        for ticket in reopened[:5]:  # Limit to 5
            ticket_url = f"{config.JIRA_URL}/browse/{ticket['ticket_key']}"
            reopened_text += f"- <{ticket_url}|{ticket['ticket_key']}>: {ticket['summary'][:50]} - {ticket['assignee']}\n"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": reopened_text}
        })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*Reopened Yesterday*\nNo tickets were reopened yesterday."}
        })

    # Stale Tickets Section
    stale = data["stale_tickets"]
    if stale:
        stale_text = f"*Stuck in Status (>{config.STALE_THRESHOLD_DAYS} days) - {len(stale)} tickets*\n"
        for ticket in stale[:5]:  # Limit to 5
            ticket_url = f"{config.JIRA_URL}/browse/{ticket['ticket_key']}"
            stale_text += f"- <{ticket_url}|{ticket['ticket_key']}>: {ticket['status']} for {ticket['days_stale']}d - {ticket['assignee']}\n"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": stale_text}
        })

    # Velocity Section
    velocity = data["velocity"]
    trend_emoji = "" if velocity["trend"] >= 0 else ""
    trend_sign = "+" if velocity["trend"] >= 0 else ""

    velocity_text = f"*Velocity This Week*\n"
    velocity_text += f"- Completed: {velocity['this_week']} tickets (vs {velocity['last_week']} last week)\n"
    velocity_text += f"- Trend: {trend_emoji} {trend_sign}{velocity['trend']}%"

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": velocity_text}
    })

    # Reopen Rate Summary
    reopen_rates = data["reopen_rates"]
    if reopen_rates:
        # Find anyone with high reopen rate (>20%)
        high_reopen = [(name, stats) for name, stats in reopen_rates.items()
                       if stats["rate"] > 20 and stats["total"] >= 3]

        if high_reopen:
            reopen_text = "*Reopen Rate Alerts (>20%, last 7 days)*\n"
            for name, stats in sorted(high_reopen, key=lambda x: -x[1]["rate"]):
                reopen_text += f"- {name}: {stats['rate']}% ({stats['reopened']}/{stats['total']} tickets)\n"

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": reopen_text}
            })

    # PRs Needing Review (if GitHub enabled)
    open_prs = data["open_prs"]
    if open_prs:
        pr_text = f"*PRs Needing Review ({len(open_prs)})*\n"
        for pr in open_prs[:3]:  # Limit to 3
            pr_url = f"https://github.com/{config.GITHUB_ORG}/{config.GITHUB_REPO}/pull/{pr['pr_number']}"
            pr_text += f"- <{pr_url}|#{pr['pr_number']}>: {pr['title'][:40]} ({pr['days_open']}d old)\n"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": pr_text}
        })

    # Dashboard link
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": f"_View full dashboard for detailed metrics_"
        }]
    })

    return blocks


def send_daily_digest():
    """Generate and send the daily digest to Slack."""
    print(f"Generating daily digest at {datetime.now().isoformat()}")

    blocks = format_daily_digest()
    success = send_slack_message(blocks, "Daily Team Insights")

    return success


def send_daily_digest_with_ai(ai_insights: str):
    """Generate and send the daily digest with AI analysis to Slack."""
    print(f"Generating daily digest with AI at {datetime.now().isoformat()}")

    data = metrics.get_daily_digest_data()
    blocks = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"Michael's Daily Assessment - {data['date']}"
        }
    })

    blocks.append({"type": "divider"})

    # AI Analysis Section (prominent at top)
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Claude's Assessment*"
        }
    })

    # Split AI insights into chunks if too long (Slack has 3000 char limit per block)
    insights_chunks = [ai_insights[i:i+2900] for i in range(0, len(ai_insights), 2900)]
    for chunk in insights_chunks[:3]:  # Max 3 blocks
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": chunk
            }
        })

    blocks.append({"type": "divider"})

    # Reopened Yesterday Section
    reopened = data["reopened_yesterday"]
    if reopened:
        reopened_text = f"*Reopened Yesterday ({len(reopened)})*\n"
        for ticket in reopened[:5]:
            ticket_url = f"{config.JIRA_URL}/browse/{ticket['ticket_key']}"
            reopened_text += f"- <{ticket_url}|{ticket['ticket_key']}>: {ticket['summary'][:50]} - {ticket['assignee']}\n"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": reopened_text}
        })

    # Stale Tickets Section (abbreviated)
    stale = data["stale_tickets"]
    if stale:
        stale_text = f"*Stuck in Status (>{config.STALE_THRESHOLD_DAYS} days)*: {len(stale)} tickets\n"
        for ticket in stale[:3]:  # Limit to 3 since AI covers detail
            ticket_url = f"{config.JIRA_URL}/browse/{ticket['ticket_key']}"
            stale_text += f"- <{ticket_url}|{ticket['ticket_key']}>: {ticket['status']} for {ticket['days_stale']}d\n"
        if len(stale) > 3:
            stale_text += f"_...and {len(stale) - 3} more_"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": stale_text}
        })

    # Quick stats
    velocity = data["velocity"]
    trend_sign = "+" if velocity["trend"] >= 0 else ""
    quick_stats = f"*Quick Stats*: {velocity['this_week']} completed this week ({trend_sign}{velocity['trend']}% vs last week)"

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": quick_stats}]
    })

    # Footer
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "_Analysis powered by Claude | View full dashboard for details_"
        }]
    })

    success = send_slack_message(blocks, "Daily Team Insights (AI-Powered)")
    return success


def format_weekly_summary() -> list:
    """Format the weekly summary as Slack blocks (for Fridays)."""
    data = metrics.get_weekly_summary_data()
    blocks = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"Michael's Weekly Assessment - Week of {data['week_of']}"
        }
    })

    blocks.append({"type": "divider"})

    # Team Totals
    totals = data["team_totals"]
    trend_emoji = "" if totals["trend"] >= 0 else ""
    trend_sign = "+" if totals["trend"] >= 0 else ""

    team_text = f"*Team Performance*\n"
    team_text += f"Tickets completed: *{totals['completed']}* (vs {totals['last_week']} last week) {trend_emoji} {trend_sign}{totals['trend']}%\n"
    team_text += f"Tickets reopened: *{totals['reopened']}* (vs {totals['reopened_last_week']} last week)"

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": team_text}
    })

    blocks.append({"type": "divider"})

    # Developer Performance Table
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*Developer Performance This Week*"}
    })

    dev_perf = data["developer_performance"]
    # Sort by completed descending
    sorted_devs = sorted(dev_perf.items(), key=lambda x: -x[1]["completed_this_week"])

    for dev, stats in sorted_devs:
        trend_sign = "+" if stats["trend"] >= 0 else ""
        trend_emoji = "" if stats["trend"] >= 0 else "" if stats["trend"] < -20 else ""

        dev_text = f"*{dev}*\n"
        dev_text += f"  Completed: {stats['completed_this_week']} ({trend_sign}{stats['trend']}% vs last week)\n"

        if stats["reopened"] > 0:
            dev_text += f"  Reopened: {stats['reopened']}\n"
        if stats["quality_issues"] > 0:
            dev_text += f"  Sent back from testing: {stats['quality_issues']}\n"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": dev_text}
        })

    # Expedite tickets alert
    expedites = data["expedite_tickets"]
    if expedites:
        blocks.append({"type": "divider"})
        exp_text = f"*Expedite Tickets Still Open ({len(expedites)})*\n"
        for t in expedites[:5]:
            ticket_url = f"{config.JIRA_URL}/browse/{t['ticket_key']}"
            exp_text += f"- <{ticket_url}|{t['ticket_key']}>: {t['status']} ({t['days_idle']}d idle) - {t['assignee']}\n"
        if len(expedites) > 5:
            exp_text += f"_...and {len(expedites) - 5} more_"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": exp_text}
        })

    # Footer
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "_Weekly summary generated automatically | View full dashboard for details_"
        }]
    })

    return blocks


def send_weekly_summary():
    """Generate and send the weekly summary to Slack."""
    print(f"Generating weekly summary at {datetime.now().isoformat()}")

    blocks = format_weekly_summary()
    success = send_slack_message(blocks, "Weekly Team Summary")

    return success


def send_weekly_summary_with_ai(ai_insights: str):
    """Generate and send weekly summary with AI analysis to Slack."""
    print(f"Generating weekly summary with AI at {datetime.now().isoformat()}")

    data = metrics.get_weekly_summary_data()
    blocks = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"Michael's Weekly Assessment - Week of {data['week_of']}"
        }
    })

    blocks.append({"type": "divider"})

    # AI Analysis Section (prominent at top)
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Claude's Weekly Assessment*"
        }
    })

    # Split AI insights into chunks if too long
    insights_chunks = [ai_insights[i:i+2900] for i in range(0, len(ai_insights), 2900)]
    for chunk in insights_chunks[:3]:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": chunk
            }
        })

    blocks.append({"type": "divider"})

    # Team Totals
    totals = data["team_totals"]
    trend_sign = "+" if totals["trend"] >= 0 else ""

    team_text = f"*Team Totals*: {totals['completed']} completed ({trend_sign}{totals['trend']}% vs last week) | {totals['reopened']} reopened"

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": team_text}
    })

    # Developer summary (compact)
    dev_perf = data["developer_performance"]
    sorted_devs = sorted(dev_perf.items(), key=lambda x: -x[1]["completed_this_week"])

    dev_lines = []
    for dev, stats in sorted_devs:
        trend_sign = "+" if stats["trend"] >= 0 else ""
        line = f"{dev}: {stats['completed_this_week']} completed"
        if stats["reopened"] > 0:
            line += f", {stats['reopened']} reopened"
        dev_lines.append(line)

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*By Developer:*\n" + "\n".join(f"• {l}" for l in dev_lines)}
    })

    # Footer
    blocks.append({"type": "divider"})
    blocks.append({
        "type": "context",
        "elements": [{
            "type": "mrkdwn",
            "text": "_Analysis powered by Claude | View full dashboard for details_"
        }]
    })

    success = send_slack_message(blocks, "Weekly Team Summary (AI-Powered)")
    return success


def send_test_message():
    """Send a test message to verify Slack integration."""
    blocks = [{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Test Message*\nSlack integration is working correctly!"
        }
    }]

    return send_slack_message(blocks, "Test Message")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        send_test_message()
    else:
        send_daily_digest()
