"""
Main entry point for the Team Performance Dashboard.

Usage:
    python main.py sync              # Sync data from Jira (and GitHub if enabled)
    python main.py sync --full       # Full historical sync
    python main.py report            # Generate full metrics report for Claude
    python main.py notify            # Send daily Slack digest (metrics only)
    python main.py notify --ai FILE  # Send digest with AI insights from file
    python main.py dashboard         # Start the web dashboard
    python main.py daily             # Run daily job (sync + notify, no AI)
    python main.py daily-ai          # Run daily job WITH Claude Code analysis
    python main.py weekly            # Send weekly summary to Slack
    python main.py weekly-ai         # Send weekly summary WITH Claude analysis
    python main.py weekly-report     # Generate weekly report for Claude
    python main.py test-slack        # Send test message to Slack
    python main.py test-standup      # Test standup analysis (shows what Claude sees)
"""

import sys
import json
from datetime import datetime
import db
import collector
import slack_notifier
import metrics
import analysis
from dashboard import app as dashboard_app


def cmd_sync(full=False):
    """Sync data from Jira and GitHub."""
    db.init_db()

    if full:
        print("Running full historical sync...")
        collector.run_full_sync()
    else:
        print("Running incremental sync (last 7 days)...")
        collector.run_full_sync(updated_since_days=7)


def cmd_report():
    """Generate a metrics report for Claude to analyze."""
    db.init_db()
    data = metrics.get_daily_digest_data()

    # Format as readable text for Claude
    report = []
    report.append(f"=== TEAM PERFORMANCE REPORT - {data['date']} ===\n")

    # Team Velocity
    v = data['velocity']
    report.append(f"TEAM VELOCITY (Tickets reaching Ready for Production):")
    report.append(f"  - This week: {v['this_week']} tickets")
    report.append(f"  - Last week: {v['last_week']} tickets")
    report.append(f"  - Trend: {v['trend']:+.1f}%\n")

    # DEVELOPER PERFORMANCE (emphasized section)
    report.append("=" * 50)
    report.append("DEVELOPER PERFORMANCE BREAKDOWN")
    report.append("=" * 50)

    dev_summary = metrics.get_developer_summary(days=7)
    workload = analysis.get_developer_workload()
    quality = analysis.get_bugs_per_developer()

    for dev, stats in sorted(dev_summary.items(), key=lambda x: -x[1]['velocity_this_week']):
        report.append(f"\n  {dev}:")
        report.append(f"    Velocity: {stats['velocity_this_week']} this week, {stats['velocity_last_week']} last week ({stats['velocity_trend']:+.1f}%)")

        # Workload
        dev_workload = workload.get(dev, {})
        if dev_workload.get("total", 0) > 0:
            report.append(f"    Current workload: {dev_workload['total']} tickets assigned")

        # Quality
        dev_quality = quality.get(dev, {})
        if dev_quality.get("bugs_found", 0) > 0:
            report.append(f"    Bugs found in testing: {dev_quality['bugs_found']} ({dev_quality['bug_rate']}% of tickets)")

        if stats['reopened'] > 0:
            report.append(f"    REOPENED: {stats['reopened']} tickets ({stats['reopen_rate']:.1f}% reopen rate)")
        if stats['avg_in_progress_hours'] > 0:
            report.append(f"    Avg time in progress: {stats['avg_in_progress_hours']:.1f} hours")
    report.append("")

    # ETA vs Actual comparisons
    eta_comparisons = analysis.compare_eta_vs_actual()
    late_deliveries = [e for e in eta_comparisons if e["days_difference"] > 0]
    if late_deliveries:
        report.append("⏰ ETA vs ACTUAL DELIVERY:")
        for e in late_deliveries[:5]:
            report.append(f"  - {e['ticket']}: ETA was {e['eta_stated']}, delivered {e['days_difference']} days late")
            if e["times_mentioned"] > 2:
                report.append(f"    (mentioned {e['times_mentioned']} times in standups)")
        report.append("")

    # Backlog prediction
    prediction = analysis.calculate_backlog_prediction()
    report.append("📊 BACKLOG FORECAST:")
    report.append(f"  - Next-Release backlog: {prediction['next_release_backlog']} tickets")
    report.append(f"  - Weekly velocity: {prediction['weekly_velocity']} tickets/week")
    report.append(f"  - Days to clear Next-Release: ~{int(prediction['days_to_clear_next_release'])} days")
    report.append("")

    # Expedite tickets (Highest priority sitting idle)
    expedites = metrics.get_expedite_tickets_idle()
    if expedites:
        report.append("🚨 EXPEDITE TICKETS SITTING IDLE (Highest Priority):")
        for t in expedites:
            report.append(f"  - {t['ticket_key']}: {t['status']} for {t['days_idle']} days - {t['assignee']}")
            report.append(f"    {t['summary'][:60]}")
        report.append("")

    # Next-Release tickets
    next_release = metrics.get_tickets_by_label("Next-Release")
    if next_release:
        report.append(f"NEXT-RELEASE TICKETS ({len(next_release)}):")
        for t in next_release[:5]:
            report.append(f"  - {t['ticket_key']}: {t['status']} - {t['assignee']}")
        report.append("")

    # Tickets reopened yesterday
    reopened = data['reopened_yesterday']
    if reopened:
        report.append(f"TICKETS REOPENED YESTERDAY ({len(reopened)}):")
        for t in reopened:
            report.append(f"  - {t['ticket_key']}: {t['summary'][:60]} (Assignee: {t['assignee']})")
        report.append("")

    # Stale tickets (categorized as new vs ongoing)
    stale_categorized = analysis.get_stale_tickets_categorized()
    if stale_categorized["total"] > 0:
        report.append(f"STALE TICKETS - NO UPDATES >3 DAYS ({stale_categorized['total']} total):")

        if stale_categorized["new"]:
            report.append(f"  NEW (just became stale):")
            for t in stale_categorized["new"][:5]:
                report.append(f"    - {t['ticket_key']}: {t['status']} for {t['days_stale']} days ({t['assignee']})")

        if stale_categorized["ongoing"]:
            report.append(f"  ONGOING (stale for a while - {len(stale_categorized['ongoing'])} tickets):")
            for t in stale_categorized["ongoing"][:3]:
                report.append(f"    - {t['ticket_key']}: {t['status']} for {t['days_stale']} days ({t['assignee']})")
            if len(stale_categorized["ongoing"]) > 3:
                report.append(f"    ... and {len(stale_categorized['ongoing']) - 3} more")
        report.append("")

    # PRs if enabled
    prs = data['open_prs']
    if prs:
        report.append(f"OPEN PULL REQUESTS ({len(prs)}):")
        for pr in prs[:5]:
            report.append(f"  - PR #{pr['pr_number']}: {pr['title'][:50]} ({pr['days_open']} days old)")
        report.append("")

    # Standup analysis (compare what devs said vs actual Jira movement)
    try:
        import slack_reader
        standup_analysis = slack_reader.format_standup_analysis_for_claude()
        report.append("\n" + standup_analysis)
    except Exception as e:
        report.append(f"\nSTANDUP ANALYSIS: Could not load - {e}")

    print("\n".join(report))


def cmd_notify(ai_insights_file=None):
    """Send daily Slack digest, optionally with AI insights."""
    db.init_db()

    if ai_insights_file:
        try:
            with open(ai_insights_file, 'r') as f:
                ai_insights = f.read().strip()
            slack_notifier.send_daily_digest_with_ai(ai_insights)
        except FileNotFoundError:
            print(f"Warning: AI insights file not found: {ai_insights_file}")
            slack_notifier.send_daily_digest()
    else:
        slack_notifier.send_daily_digest()


def cmd_dashboard(production=False):
    """Start the web dashboard."""
    if production:
        dashboard_app.run_production()
    else:
        dashboard_app.run_server()


def cmd_daily():
    """Run full daily job: sync + notify."""
    print("=" * 50)
    print("Running daily job...")
    print("=" * 50)

    # Sync recent data
    cmd_sync(full=False)

    # Send Slack notification
    cmd_notify()

    print("=" * 50)
    print("Daily job complete!")
    print("=" * 50)


def cmd_test_slack():
    """Send test message to Slack."""
    slack_notifier.send_test_message()


def cmd_test_standup():
    """Test standup analysis - shows what Claude will see."""
    db.init_db()
    try:
        import slack_reader
        print(slack_reader.format_standup_analysis_for_claude())
    except Exception as e:
        print(f"Error testing standup analysis: {e}")
        print("\nMake sure you have set these in your .env file:")
        print("  SLACK_BOT_TOKEN=xoxb-...")
        print("  SLACK_STANDUP_CHANNEL_ID=C...")


def cmd_weekly_report():
    """Generate a weekly report for Claude to analyze."""
    db.init_db()
    data = metrics.get_weekly_summary_data()
    dev_summary = metrics.get_developer_summary(days=7)
    quality = analysis.get_bugs_per_developer()
    prediction = analysis.calculate_backlog_prediction()

    report = []
    report.append(f"=== WEEKLY TEAM SUMMARY - Week of {data['week_of']} ===\n")

    # Team Totals
    totals = data["team_totals"]
    report.append("TEAM TOTALS:")
    report.append(f"  - Tickets completed: {totals['completed']} (vs {totals['last_week']} last week)")
    if totals['last_week'] > 0:
        trend = ((totals['completed'] - totals['last_week']) / totals['last_week']) * 100
        report.append(f"  - Week-over-week change: {trend:+.1f}%")
    report.append(f"  - Tickets reopened: {totals['reopened']} (vs {totals['reopened_last_week']} last week)")
    report.append("")

    # Developer Performance
    report.append("=" * 50)
    report.append("DEVELOPER PERFORMANCE (This Week)")
    report.append("=" * 50)

    dev_perf = data["developer_performance"]
    sorted_devs = sorted(dev_perf.items(), key=lambda x: -x[1]["completed_this_week"])

    for dev, stats in sorted_devs:
        report.append(f"\n  {dev}:")
        report.append(f"    Completed: {stats['completed_this_week']} tickets ({stats['trend']:+.1f}% vs last week)")

        # Quality metrics
        dev_quality = quality.get(dev, {})
        if stats["reopened"] > 0:
            report.append(f"    Reopened: {stats['reopened']} tickets")
        if stats["quality_issues"] > 0:
            report.append(f"    Sent back from testing: {stats['quality_issues']} tickets")
        if dev_quality.get("bug_rate", 0) > 15:
            report.append(f"    Bug rate: {dev_quality['bug_rate']}% (above threshold)")

        # Workload
        workload = analysis.get_developer_workload().get(dev, {})
        if workload.get("total", 0) > 0:
            report.append(f"    Current workload: {workload['total']} tickets assigned")

    report.append("")

    # Expedite Tickets
    expedites = data["expedite_tickets"]
    if expedites:
        report.append("EXPEDITE TICKETS (Highest Priority - Still Open):")
        for t in expedites:
            report.append(f"  - {t['ticket_key']}: {t['status']} for {t['days_idle']}d - {t['assignee']}")
            report.append(f"    {t['summary'][:60]}")
        report.append("")

    # Backlog Forecast
    report.append("BACKLOG FORECAST:")
    report.append(f"  - Next-Release backlog: {prediction['next_release_backlog']} tickets")
    report.append(f"  - Total backlog: {prediction['total_backlog']} tickets")
    report.append(f"  - Weekly velocity: {prediction['weekly_velocity']} tickets/week")
    report.append(f"  - Days to clear Next-Release: ~{int(prediction['days_to_clear_next_release'])} days")
    report.append("")

    # ETA Comparisons
    eta_comparisons = analysis.compare_eta_vs_actual()
    late_deliveries = [e for e in eta_comparisons if e["days_difference"] > 0]
    if late_deliveries:
        report.append("ETA vs ACTUAL DELIVERY (Late This Week):")
        for e in late_deliveries[:5]:
            report.append(f"  - {e['ticket']}: ETA was {e['eta_stated']}, delivered {e['days_difference']} days late ({e['stated_by']})")
        report.append("")

    # Standup Analysis
    try:
        import slack_reader
        standup_analysis = slack_reader.format_standup_analysis_for_claude()
        report.append("\n" + standup_analysis)
    except Exception as e:
        report.append(f"\nSTANDUP ANALYSIS: Could not load - {e}")

    print("\n".join(report))


def cmd_weekly(ai_insights_file=None):
    """Send weekly summary to Slack."""
    db.init_db()

    if ai_insights_file:
        try:
            with open(ai_insights_file, 'r') as f:
                ai_insights = f.read().strip()
            slack_notifier.send_weekly_summary_with_ai(ai_insights)
        except FileNotFoundError:
            print(f"Warning: AI insights file not found: {ai_insights_file}")
            slack_notifier.send_weekly_summary()
    else:
        slack_notifier.send_weekly_summary()


def cmd_weekly_ai():
    """Run weekly job with Claude Code analysis."""
    import subprocess
    import os

    print("=" * 50)
    print("Running weekly summary with AI analysis...")
    print("=" * 50)

    # Sync recent data
    cmd_sync(full=False)

    # Generate weekly report for Claude
    print("\nGenerating weekly report...")
    report_file = "weekly_report.txt"
    with open(report_file, 'w') as f:
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            cmd_weekly_report()
        report_content = buffer.getvalue()
        f.write(report_content)

    # Call Claude Code for analysis
    print("\nAsking Claude for weekly analysis...")
    insights_file = "weekly_ai_insights.txt"

    prompt = f"""You are an assistant helping Michael Place, the delivery and test lead, analyze his team's weekly performance.
Note: Michael Place in the data is the lead himself - focus analysis on the developers (Deep, Meet, Devansh) and tester (Vipin).

Based on this weekly report, provide a comprehensive assessment (5-8 bullet points) covering:

1. WINS: What went well this week? Who performed above expectations?
2. CONCERNS: Quality issues, high reopen rates, or developers struggling
3. PATTERNS: Any recurring issues? Same tickets being mentioned repeatedly?
4. STANDUPS vs REALITY: Discrepancies between what was stated and actual Jira movement
5. EXPEDITE STATUS: Are Highest-priority tickets getting proper attention?
6. FORECAST: Based on current velocity, are we on track for upcoming milestones?
7. RECOMMENDATIONS: 2-3 specific actions for next week

Be direct and specific. Use ticket numbers and developer names.
Highlight both good performance and areas needing attention.

IMPORTANT FORMATTING RULES (this will be posted to Slack):
- Use *text* for bold (single asterisk, NOT double)
- Use _text_ for italic (underscore)
- Use plain text emojis like :white_check_mark: :warning: :rocket: :chart_with_upwards_trend: :red_circle:
- Use bullet points with - or *
- Keep it concise and scannable
- Do NOT use markdown headers (no # or ##)

Here's the data:

{report_content}"""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--print"],
            capture_output=True,
            text=True,
            timeout=180  # Longer timeout for weekly analysis
        )

        if result.returncode == 0 and result.stdout.strip():
            with open(insights_file, 'w') as f:
                f.write(result.stdout.strip())
            print("Claude analysis complete!")
        else:
            print(f"Claude Code returned no output or error: {result.stderr}")
            insights_file = None
    except FileNotFoundError:
        print("Claude Code not found. Install with: npm install -g @anthropic-ai/claude-code")
        insights_file = None
    except subprocess.TimeoutExpired:
        print("Claude Code timed out")
        insights_file = None
    except Exception as e:
        print(f"Error running Claude Code: {e}")
        insights_file = None

    # Send notification
    print("\nSending Slack notification...")
    cmd_weekly(ai_insights_file=insights_file)

    # Cleanup temp files
    for f in [report_file, insights_file]:
        if f and os.path.exists(f):
            os.remove(f)

    print("=" * 50)
    print("Weekly summary with AI complete!")
    print("=" * 50)


def print_usage():
    """Print usage instructions."""
    print(__doc__)


def cmd_daily_ai():
    """Run daily job with Claude Code analysis."""
    import subprocess
    import os

    print("=" * 50)
    print("Running daily job with AI analysis...")
    print("=" * 50)

    # Sync recent data
    cmd_sync(full=False)

    # Generate report for Claude
    print("\nGenerating metrics report...")
    report_file = "metrics_report.txt"
    with open(report_file, 'w') as f:
        # Capture report output
        import io
        from contextlib import redirect_stdout
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            cmd_report()
        report_content = buffer.getvalue()
        f.write(report_content)

    # Call Claude Code for analysis
    print("\nAsking Claude for analysis...")
    insights_file = "ai_insights.txt"

    prompt = f"""You are an assistant helping Michael Place, the delivery and test lead, analyze his team's performance.
Note: Michael Place in the data is the lead himself - focus analysis on the developers (Deep, Meet, Devansh) and tester (Vipin).

Based on this report, provide a brief assessment (4-6 bullet points) covering:
1. Risk flags or blockers needing immediate attention
2. IMPORTANT: Discrepancies between what devs said in standups vs actual Jira movement
   - Call out anyone who mentioned working on a ticket but it hasn't moved
   - Note if tickets moved but weren't mentioned in standups
3. Team performance patterns (who might be struggling, quality concerns, reopen patterns)
4. One specific actionable recommendation for today
5. If there is a message to 1 or more team members which might be helpful to progress or clarify things, please include a draft suggestion of this message for michael to easily copy and use if necessary.
6. Make a note of the ammount of tickets in the ready for testing column.

Be direct and specific. Reference ticket numbers and developer names.
If you see a mismatch between stated work and actual progress, flag it clearly.

IMPORTANT FORMATTING RULES (this will be posted to Slack):
- Use *text* for bold (single asterisk, NOT double)
- Use _text_ for italic (underscore)
- Use plain text emojis like :white_check_mark: :warning: :rocket: :chart_with_upwards_trend: :red_circle:
- Use bullet points with - or *
- Keep it concise and scannable
- Do NOT use markdown headers (no # or ##)

Here's the data:

{report_content}"""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--print"],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0 and result.stdout.strip():
            with open(insights_file, 'w') as f:
                f.write(result.stdout.strip())
            print("Claude analysis complete!")
        else:
            print(f"Claude Code returned no output or error: {result.stderr}")
            insights_file = None
    except FileNotFoundError:
        print("Claude Code not found. Install with: npm install -g @anthropic-ai/claude-code")
        insights_file = None
    except subprocess.TimeoutExpired:
        print("Claude Code timed out")
        insights_file = None
    except Exception as e:
        print(f"Error running Claude Code: {e}")
        insights_file = None

    # Send notification
    print("\nSending Slack notification...")
    cmd_notify(ai_insights_file=insights_file)

    # Cleanup temp files
    for f in [report_file, insights_file]:
        if f and os.path.exists(f):
            os.remove(f)

    print("=" * 50)
    print("Daily job with AI complete!")
    print("=" * 50)


def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1].lower()

    if command == "sync":
        full = "--full" in sys.argv
        cmd_sync(full=full)
    elif command == "report":
        cmd_report()
    elif command == "notify":
        # Check for --ai flag
        ai_file = None
        if "--ai" in sys.argv:
            ai_idx = sys.argv.index("--ai")
            if ai_idx + 1 < len(sys.argv):
                ai_file = sys.argv[ai_idx + 1]
        cmd_notify(ai_insights_file=ai_file)
    elif command == "dashboard":
        production = "--production" in sys.argv
        cmd_dashboard(production=production)
    elif command == "daily":
        cmd_daily()
    elif command == "daily-ai":
        cmd_daily_ai()
    elif command == "weekly":
        # Check for --ai flag
        ai_file = None
        if "--ai" in sys.argv:
            ai_idx = sys.argv.index("--ai")
            if ai_idx + 1 < len(sys.argv):
                ai_file = sys.argv[ai_idx + 1]
        cmd_weekly(ai_insights_file=ai_file)
    elif command == "weekly-ai":
        cmd_weekly_ai()
    elif command == "weekly-report":
        cmd_weekly_report()
    elif command == "test-slack":
        cmd_test_slack()
    elif command == "test-standup":
        cmd_test_standup()
    else:
        print(f"Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    main()
