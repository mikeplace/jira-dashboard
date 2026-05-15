"""
Advanced analysis functions for team performance insights.
"""

import re
from datetime import datetime, timedelta
from collections import defaultdict
from dateutil import parser as date_parser
import db
import config


def parse_datetime(dt_string: str):
    """Parse ISO datetime string to datetime object."""
    if not dt_string:
        return None
    try:
        return date_parser.isoparse(dt_string).replace(tzinfo=None)
    except Exception:
        return None


def jira_link(ticket_key: str) -> str:
    """Generate a Slack-formatted Jira link."""
    url = f"{config.JIRA_URL}/browse/{ticket_key}"
    return f"<{url}|{ticket_key}>"


def extract_etas_from_standups(updates: list) -> dict:
    """
    Extract ETAs mentioned in standup messages.
    Returns: {ticket_key: [(stated_date, stated_by, message_date), ...]}
    """
    etas = defaultdict(list)

    # Pattern to match "ETA 14 May 2026" or "ETA: 14 May" or "ETA 14/05"
    eta_patterns = [
        rf'({config.JIRA_PROJECT_KEY}-\d+)[:\s]+.*?ETA[:\s]+(\d{{1,2}}[\s/]\w+[\s/]?\d{{0,4}})',
        rf'({config.JIRA_PROJECT_KEY}-\d+).*?ETA[:\s]+(\d{{1,2}}[\s/]\w+[\s/]?\d{{0,4}})',
    ]

    for update in updates:
        text = update.get("raw_text", "")
        msg_date = update.get("datetime", "")[:10]
        user = update.get("user", "Unknown")

        for pattern in eta_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for ticket, eta_str in matches:
                ticket = ticket.upper()
                etas[ticket].append({
                    "eta_stated": eta_str.strip(),
                    "stated_by": user,
                    "stated_on": msg_date
                })

    return dict(etas)


def compare_eta_vs_actual() -> list:
    """
    Compare stated ETAs with actual completion dates.
    Returns list of discrepancies.
    """
    try:
        import slack_reader
        reader = slack_reader.SlackReader()
        updates = reader.parse_daily_updates(hours=7*24)  # Last 7 days
    except Exception:
        return []

    etas = extract_etas_from_standups(updates)

    conn = db.get_connection()
    cursor = conn.cursor()

    comparisons = []

    for ticket_key, eta_list in etas.items():
        # Get when ticket actually reached Ready for Production or Done
        cursor.execute("""
            SELECT transitioned_at FROM status_transitions
            WHERE ticket_key = ? AND to_status IN ('Ready for Production', 'Done')
            ORDER BY transitioned_at DESC LIMIT 1
        """, (ticket_key,))
        row = cursor.fetchone()

        if row and eta_list:
            actual_date = row["transitioned_at"][:10]
            first_eta = eta_list[0]  # First stated ETA

            # Try to parse ETA date
            try:
                # Handle various formats
                eta_str = first_eta["eta_stated"]
                # Add current year if not present
                if not re.search(r'\d{4}', eta_str):
                    eta_str += f" {datetime.now().year}"
                eta_parsed = date_parser.parse(eta_str, fuzzy=True)
                actual_parsed = date_parser.parse(actual_date)

                days_diff = (actual_parsed - eta_parsed).days

                comparisons.append({
                    "ticket": ticket_key,
                    "eta_stated": first_eta["eta_stated"],
                    "stated_by": first_eta["stated_by"],
                    "actual_completion": actual_date,
                    "days_difference": days_diff,
                    "on_time": days_diff <= 0,
                    "times_mentioned": len(eta_list)
                })
            except Exception:
                pass

    conn.close()

    # Sort by most late first
    return sorted(comparisons, key=lambda x: -x["days_difference"])


def get_stale_tickets_categorized() -> dict:
    """
    Categorize stale tickets into 'new' (became stale in last 2 days) vs 'ongoing'.
    """
    stale = db.get_stale_tickets(config.STALE_THRESHOLD_DAYS)

    now = datetime.utcnow()
    threshold = now - timedelta(days=config.STALE_THRESHOLD_DAYS)

    new_stale = []
    ongoing_stale = []

    for ticket in stale:
        updated = parse_datetime(ticket.get("updated_at"))
        if updated:
            days_stale = (now - updated).days
            ticket["days_stale"] = days_stale

            # If it became stale in the last 2 days (just crossed threshold)
            if days_stale <= config.STALE_THRESHOLD_DAYS + 2:
                ticket["category"] = "new"
                new_stale.append(ticket)
            else:
                ticket["category"] = "ongoing"
                ongoing_stale.append(ticket)
        else:
            ticket["days_stale"] = 0
            ongoing_stale.append(ticket)

    return {
        "new": new_stale,
        "ongoing": ongoing_stale,
        "total": len(stale)
    }


def get_developer_workload() -> dict:
    """
    Get current workload per developer (tickets assigned, by status).
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT assignee, status, COUNT(*) as count
        FROM tickets
        WHERE status NOT IN ('Done', 'Ready for Production', 'Closed')
        GROUP BY assignee, status
    """)

    workload = defaultdict(lambda: {"total": 0, "by_status": {}})

    for row in cursor.fetchall():
        assignee = row["assignee"]
        if assignee == "Unassigned":
            continue
        status = row["status"]
        count = row["count"]

        workload[assignee]["total"] += count
        workload[assignee]["by_status"][status] = count

    conn.close()
    return dict(workload)


def get_bugs_per_developer() -> dict:
    """
    Track bugs/issues found during testing, attributed to the developer.
    Uses reopen count and tickets that went backwards in workflow.
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    # Get tickets that were reopened or sent back from testing
    cursor.execute("""
        SELECT t.assignee, COUNT(DISTINCT st.ticket_key) as bugs_found
        FROM status_transitions st
        JOIN tickets t ON st.ticket_key = t.ticket_key
        WHERE st.to_status IN ('Re-opened', 'Reopened', 'In Progress')
        AND st.from_status IN ('Ready for Testing', 'Dev Checks', 'Ready for Production')
        AND st.transitioned_at >= date('now', '-30 days')
        GROUP BY t.assignee
    """)

    bugs = {}
    for row in cursor.fetchall():
        if row["assignee"] and row["assignee"] != "Unassigned":
            bugs[row["assignee"]] = row["bugs_found"]

    # Also get total tickets tested per dev for ratio
    cursor.execute("""
        SELECT t.assignee, COUNT(DISTINCT st.ticket_key) as tested
        FROM status_transitions st
        JOIN tickets t ON st.ticket_key = t.ticket_key
        WHERE st.to_status = 'Ready for Testing'
        AND st.transitioned_at >= date('now', '-30 days')
        GROUP BY t.assignee
    """)

    tested = {}
    for row in cursor.fetchall():
        if row["assignee"] and row["assignee"] != "Unassigned":
            tested[row["assignee"]] = row["tested"]

    conn.close()

    # Combine into quality metrics
    quality = {}
    all_devs = set(bugs.keys()) | set(tested.keys())
    for dev in all_devs:
        dev_bugs = bugs.get(dev, 0)
        dev_tested = tested.get(dev, 0)
        quality[dev] = {
            "bugs_found": dev_bugs,
            "tickets_tested": dev_tested,
            "bug_rate": round((dev_bugs / dev_tested * 100), 1) if dev_tested > 0 else 0
        }

    return quality


def calculate_backlog_prediction() -> dict:
    """
    Predict when current backlog will be cleared based on recent velocity.
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    # Current backlog (not Done/Ready for Production)
    cursor.execute("""
        SELECT COUNT(*) as count FROM tickets
        WHERE status NOT IN ('Done', 'Ready for Production', 'Closed')
        AND labels LIKE '%Next-Release%'
    """)
    next_release_backlog = cursor.fetchone()["count"]

    cursor.execute("""
        SELECT COUNT(*) as count FROM tickets
        WHERE status NOT IN ('Done', 'Ready for Production', 'Closed')
    """)
    total_backlog = cursor.fetchone()["count"]

    # Recent velocity (last 2 weeks average per week)
    two_weeks_ago = (datetime.utcnow() - timedelta(days=14)).isoformat()
    cursor.execute("""
        SELECT COUNT(DISTINCT ticket_key) as count
        FROM status_transitions
        WHERE to_status = 'Ready for Production'
        AND transitioned_at >= ?
    """, (two_weeks_ago,))
    completed_2_weeks = cursor.fetchone()["count"]
    weekly_velocity = completed_2_weeks / 2 if completed_2_weeks > 0 else 1

    conn.close()

    # Calculate days to clear
    days_to_clear_next_release = (next_release_backlog / weekly_velocity * 7) if weekly_velocity > 0 else 999
    days_to_clear_total = (total_backlog / weekly_velocity * 7) if weekly_velocity > 0 else 999

    return {
        "next_release_backlog": next_release_backlog,
        "total_backlog": total_backlog,
        "weekly_velocity": round(weekly_velocity, 1),
        "days_to_clear_next_release": round(days_to_clear_next_release, 0),
        "days_to_clear_total": round(days_to_clear_total, 0)
    }


def get_full_analysis() -> dict:
    """Get all advanced analysis data."""
    return {
        "eta_comparisons": compare_eta_vs_actual(),
        "stale_categorized": get_stale_tickets_categorized(),
        "developer_workload": get_developer_workload(),
        "quality_metrics": get_bugs_per_developer(),
        "backlog_prediction": calculate_backlog_prediction()
    }
