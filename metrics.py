"""
Metrics calculations for team performance dashboard.
"""

from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional
from dateutil import parser as date_parser
import db
import config


def parse_datetime(dt_string: str) -> Optional[datetime]:
    """Parse ISO datetime string to datetime object."""
    if not dt_string:
        return None
    try:
        return date_parser.isoparse(dt_string).replace(tzinfo=None)
    except Exception:
        return None


def calculate_reopen_rate(days: int = 30) -> dict:
    """
    Calculate reopen rate per assignee.
    Returns: {assignee: {"total": N, "reopened": N, "rate": X%}}
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    # Get tickets that had activity in the period
    cursor.execute("""
        SELECT assignee, COUNT(*) as total, SUM(reopen_count) as reopened
        FROM tickets
        WHERE updated_at >= ?
        GROUP BY assignee
    """, (cutoff,))

    results = {}
    for row in cursor.fetchall():
        assignee = row["assignee"]
        total = row["total"]
        reopened = row["reopened"] or 0
        rate = (reopened / total * 100) if total > 0 else 0

        results[assignee] = {
            "total": total,
            "reopened": reopened,
            "rate": round(rate, 1)
        }

    conn.close()
    return results


def calculate_time_in_status(days: int = 30) -> dict:
    """
    Calculate average time spent in each status, grouped by assignee.
    Returns: {assignee: {status: avg_hours}}
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    # Get all transitions in the period
    cursor.execute("""
        SELECT st.ticket_key, st.from_status, st.to_status, st.transitioned_at, t.assignee
        FROM status_transitions st
        JOIN tickets t ON st.ticket_key = t.ticket_key
        WHERE st.transitioned_at >= ?
        ORDER BY st.ticket_key, st.transitioned_at
    """, (cutoff,))

    transitions = cursor.fetchall()
    conn.close()

    # Group transitions by ticket
    ticket_transitions = defaultdict(list)
    ticket_assignees = {}

    for row in transitions:
        ticket_key = row["ticket_key"]
        ticket_transitions[ticket_key].append({
            "from_status": row["from_status"],
            "to_status": row["to_status"],
            "transitioned_at": parse_datetime(row["transitioned_at"])
        })
        ticket_assignees[ticket_key] = row["assignee"]

    # Calculate time in each status
    assignee_status_times = defaultdict(lambda: defaultdict(list))

    for ticket_key, trans_list in ticket_transitions.items():
        assignee = ticket_assignees[ticket_key]

        for i, trans in enumerate(trans_list):
            if i == 0:
                continue  # Skip first transition (no "from" time)

            prev_trans = trans_list[i - 1]
            from_time = prev_trans["transitioned_at"]
            to_time = trans["transitioned_at"]

            if from_time and to_time:
                duration_hours = (to_time - from_time).total_seconds() / 3600
                status = prev_trans["to_status"]
                assignee_status_times[assignee][status].append(duration_hours)

    # Calculate averages
    results = {}
    for assignee, status_times in assignee_status_times.items():
        results[assignee] = {}
        for status, times in status_times.items():
            if times:
                avg_hours = sum(times) / len(times)
                results[assignee][status] = round(avg_hours, 1)

    return results


def get_tickets_reopened_since(since_date: datetime) -> list:
    """Get tickets that were reopened since a given date."""
    transitions = db.get_all_transitions_since(since_date.isoformat())

    reopened = []
    for trans in transitions:
        if trans["to_status"] == config.REOPEN_STATUS:
            reopened.append({
                "ticket_key": trans["ticket_key"],
                "summary": trans["summary"],
                "assignee": trans["assignee"],
                "reopened_at": trans["transitioned_at"],
                "reopened_by": trans["transitioned_by"]
            })

    return reopened


def get_stale_tickets(threshold_days: int = None) -> list:
    """Get tickets stuck in the same status for too long."""
    if threshold_days is None:
        threshold_days = config.STALE_THRESHOLD_DAYS

    stale = db.get_stale_tickets(threshold_days)

    # Calculate days stale
    now = datetime.utcnow()
    for ticket in stale:
        updated = parse_datetime(ticket["updated_at"])
        if updated:
            ticket["days_stale"] = (now - updated).days
        else:
            ticket["days_stale"] = 0

    return sorted(stale, key=lambda x: x["days_stale"], reverse=True)


def calculate_velocity(weeks: int = 2) -> dict:
    """
    Calculate tickets reaching 'Ready for Production' per week.
    Returns: {"this_week": N, "last_week": N, "trend": +/-N%}
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    now = datetime.utcnow()
    this_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start

    # This week - tickets that transitioned to "Ready for Production"
    cursor.execute("""
        SELECT COUNT(DISTINCT ticket_key) as count
        FROM status_transitions
        WHERE to_status = 'Ready for Production'
        AND transitioned_at >= ?
    """, (this_week_start.isoformat(),))
    this_week = cursor.fetchone()["count"]

    # Last week - tickets that transitioned to "Ready for Production"
    cursor.execute("""
        SELECT COUNT(DISTINCT ticket_key) as count
        FROM status_transitions
        WHERE to_status = 'Ready for Production'
        AND transitioned_at >= ? AND transitioned_at < ?
    """, (last_week_start.isoformat(), last_week_end.isoformat()))
    last_week = cursor.fetchone()["count"]

    conn.close()

    # Calculate trend
    if last_week > 0:
        trend = ((this_week - last_week) / last_week) * 100
    else:
        trend = 100 if this_week > 0 else 0

    return {
        "this_week": this_week,
        "last_week": last_week,
        "trend": round(trend, 1)
    }


def get_expedite_tickets_idle() -> list:
    """
    Get "Highest" priority tickets that are sitting idle.
    These should never spend days without being picked up.
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    # Find Highest priority tickets not in Done/Ready for Production
    cursor.execute("""
        SELECT ticket_key, summary, assignee, status, priority, updated_at
        FROM tickets
        WHERE priority = 'Highest'
        AND status NOT IN ('Done', 'Ready for Production')
        ORDER BY updated_at ASC
    """)

    expedites = []
    now = datetime.utcnow()

    for row in cursor.fetchall():
        updated = parse_datetime(row["updated_at"])
        if updated:
            days_idle = (now - updated).days
        else:
            days_idle = 0

        # Flag if idle for more than 1 day
        if days_idle >= 1:
            expedites.append({
                "ticket_key": row["ticket_key"],
                "summary": row["summary"],
                "assignee": row["assignee"],
                "status": row["status"],
                "days_idle": days_idle
            })

    conn.close()
    return expedites


def get_tickets_by_label(label: str) -> list:
    """Get tickets with a specific label (e.g., 'Next-Release', 'Next-Up')."""
    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ticket_key, summary, assignee, status, labels, updated_at
        FROM tickets
        WHERE labels LIKE ?
        AND status NOT IN ('Done', 'Ready for Production')
    """, (f'%{label}%',))

    tickets = []
    for row in cursor.fetchall():
        tickets.append({
            "ticket_key": row["ticket_key"],
            "summary": row["summary"],
            "assignee": row["assignee"],
            "status": row["status"]
        })

    conn.close()
    return tickets


def calculate_developer_velocity(days: int = 7) -> dict:
    """
    Calculate per-developer velocity (tickets reaching Ready for Production).
    Returns: {developer: {"this_week": N, "last_week": N, "trend": X%}}
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    now = datetime.utcnow()
    this_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start

    # Get transitions to Ready for Production, grouped by ticket's assignee
    cursor.execute("""
        SELECT t.assignee, COUNT(DISTINCT st.ticket_key) as count
        FROM status_transitions st
        JOIN tickets t ON st.ticket_key = t.ticket_key
        WHERE st.to_status = 'Ready for Production'
        AND st.transitioned_at >= ?
        GROUP BY t.assignee
    """, (this_week_start.isoformat(),))

    this_week_data = {row["assignee"]: row["count"] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT t.assignee, COUNT(DISTINCT st.ticket_key) as count
        FROM status_transitions st
        JOIN tickets t ON st.ticket_key = t.ticket_key
        WHERE st.to_status = 'Ready for Production'
        AND st.transitioned_at >= ? AND st.transitioned_at < ?
        GROUP BY t.assignee
    """, (last_week_start.isoformat(), last_week_end.isoformat()))

    last_week_data = {row["assignee"]: row["count"] for row in cursor.fetchall()}

    conn.close()

    # Combine into per-developer stats
    all_devs = set(this_week_data.keys()) | set(last_week_data.keys())
    results = {}

    for dev in all_devs:
        if dev == "Unassigned":
            continue
        this_week = this_week_data.get(dev, 0)
        last_week = last_week_data.get(dev, 0)

        if last_week > 0:
            trend = ((this_week - last_week) / last_week) * 100
        else:
            trend = 100 if this_week > 0 else 0

        results[dev] = {
            "this_week": this_week,
            "last_week": last_week,
            "trend": round(trend, 1)
        }

    return results


def get_developer_summary(days: int = 7) -> dict:
    """
    Comprehensive developer performance summary.
    """
    dev_velocity = calculate_developer_velocity(days)
    reopen_rates = calculate_reopen_rate(days)
    time_in_status = calculate_time_in_status(days)

    # Combine into per-developer summary
    all_devs = set(dev_velocity.keys()) | set(reopen_rates.keys())
    summaries = {}

    for dev in all_devs:
        if dev == "Unassigned":
            continue

        vel = dev_velocity.get(dev, {"this_week": 0, "last_week": 0, "trend": 0})
        reopen = reopen_rates.get(dev, {"total": 0, "reopened": 0, "rate": 0})
        time_stats = time_in_status.get(dev, {})

        # Calculate average cycle time (In Progress to Ready for Production)
        in_progress_time = time_stats.get("In Progress", 0)

        summaries[dev] = {
            "velocity_this_week": vel["this_week"],
            "velocity_last_week": vel["last_week"],
            "velocity_trend": vel["trend"],
            "tickets_touched": reopen["total"],
            "reopened": reopen["reopened"],
            "reopen_rate": reopen["rate"],
            "avg_in_progress_hours": in_progress_time
        }

    return summaries


def get_open_prs_needing_review() -> list:
    """Get open PRs that may need attention."""
    if not config.GITHUB_ENABLED:
        return []

    conn = db.get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM pull_requests
        WHERE state = 'open'
        ORDER BY created_at ASC
    """)

    prs = []
    now = datetime.utcnow()

    for row in cursor.fetchall():
        created = parse_datetime(row["created_at"])
        if created:
            days_open = (now - created).days
        else:
            days_open = 0

        prs.append({
            "pr_number": row["pr_number"],
            "title": row["title"],
            "author": row["author"],
            "days_open": days_open,
            "linked_ticket": row["linked_ticket"]
        })

    conn.close()
    return prs


def get_dashboard_summary() -> dict:
    """
    Get all metrics for dashboard display.
    Returns a comprehensive summary for the UI.
    """
    return {
        "reopen_rates": calculate_reopen_rate(30),
        "time_in_status": calculate_time_in_status(30),
        "velocity": calculate_velocity(),
        "stale_tickets": get_stale_tickets(),
        "open_prs": get_open_prs_needing_review(),
        "generated_at": datetime.utcnow().isoformat()
    }


def get_daily_digest_data() -> dict:
    """
    Get data specifically formatted for the daily Slack digest.
    """
    yesterday = datetime.utcnow() - timedelta(days=1)

    return {
        "reopened_yesterday": get_tickets_reopened_since(yesterday),
        "stale_tickets": get_stale_tickets()[:10],  # Top 10 most stale
        "velocity": calculate_velocity(),
        "reopen_rates": calculate_reopen_rate(7),  # Last 7 days for daily
        "open_prs": get_open_prs_needing_review()[:5],  # Top 5 PRs
        "date": datetime.utcnow().strftime("%B %d, %Y")
    }


def get_weekly_summary_data() -> dict:
    """
    Get data for the weekly summary report (Fridays).
    Covers the full week's activity with comparisons.
    """
    conn = db.get_connection()
    cursor = conn.cursor()

    now = datetime.utcnow()
    # This week (Monday to now)
    this_week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
    # Last week
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start

    # Tickets completed this week (Ready for Production)
    cursor.execute("""
        SELECT t.assignee, COUNT(DISTINCT st.ticket_key) as count
        FROM status_transitions st
        JOIN tickets t ON st.ticket_key = t.ticket_key
        WHERE st.to_status = 'Ready for Production'
        AND st.transitioned_at >= ?
        GROUP BY t.assignee
    """, (this_week_start.isoformat(),))
    completed_by_dev = {row["assignee"]: row["count"] for row in cursor.fetchall()}

    # Last week for comparison
    cursor.execute("""
        SELECT t.assignee, COUNT(DISTINCT st.ticket_key) as count
        FROM status_transitions st
        JOIN tickets t ON st.ticket_key = t.ticket_key
        WHERE st.to_status = 'Ready for Production'
        AND st.transitioned_at >= ? AND st.transitioned_at < ?
        GROUP BY t.assignee
    """, (last_week_start.isoformat(), last_week_end.isoformat()))
    last_week_by_dev = {row["assignee"]: row["count"] for row in cursor.fetchall()}

    # Reopened this week
    cursor.execute("""
        SELECT t.assignee, COUNT(DISTINCT st.ticket_key) as count
        FROM status_transitions st
        JOIN tickets t ON st.ticket_key = t.ticket_key
        WHERE st.to_status = 'Re-opened'
        AND st.transitioned_at >= ?
        GROUP BY t.assignee
    """, (this_week_start.isoformat(),))
    reopened_by_dev = {row["assignee"]: row["count"] for row in cursor.fetchall()}

    # Total reopens this week vs last week
    cursor.execute("""
        SELECT COUNT(DISTINCT ticket_key) as count
        FROM status_transitions
        WHERE to_status = 'Re-opened'
        AND transitioned_at >= ?
    """, (this_week_start.isoformat(),))
    total_reopens_this_week = cursor.fetchone()["count"]

    cursor.execute("""
        SELECT COUNT(DISTINCT ticket_key) as count
        FROM status_transitions
        WHERE to_status = 'Re-opened'
        AND transitioned_at >= ? AND transitioned_at < ?
    """, (last_week_start.isoformat(), last_week_end.isoformat()))
    total_reopens_last_week = cursor.fetchone()["count"]

    # Expedite tickets status
    cursor.execute("""
        SELECT ticket_key, summary, assignee, status, updated_at
        FROM tickets
        WHERE priority = 'Highest'
        AND status NOT IN ('Done', 'Ready for Production')
    """)
    expedites = []
    for row in cursor.fetchall():
        updated = parse_datetime(row["updated_at"])
        days_idle = (now - updated).days if updated else 0
        expedites.append({
            "ticket_key": row["ticket_key"],
            "summary": row["summary"],
            "assignee": row["assignee"],
            "status": row["status"],
            "days_idle": days_idle
        })

    # Calculate quality issues (bugs sent back from testing)
    cursor.execute("""
        SELECT t.assignee, COUNT(DISTINCT st.ticket_key) as count
        FROM status_transitions st
        JOIN tickets t ON st.ticket_key = t.ticket_key
        WHERE st.to_status IN ('Re-opened', 'In Progress')
        AND st.from_status IN ('Ready for Testing', 'Dev Checks', 'Ready for Production')
        AND st.transitioned_at >= ?
        GROUP BY t.assignee
    """, (this_week_start.isoformat(),))
    quality_issues_by_dev = {row["assignee"]: row["count"] for row in cursor.fetchall()}

    conn.close()

    # Build developer performance summary
    all_devs = set(completed_by_dev.keys()) | set(reopened_by_dev.keys()) | set(last_week_by_dev.keys())
    dev_performance = {}

    for dev in all_devs:
        if dev == "Unassigned":
            continue
        this_week = completed_by_dev.get(dev, 0)
        last_week = last_week_by_dev.get(dev, 0)
        reopened = reopened_by_dev.get(dev, 0)
        quality_issues = quality_issues_by_dev.get(dev, 0)

        if last_week > 0:
            trend = ((this_week - last_week) / last_week) * 100
        else:
            trend = 100 if this_week > 0 else 0

        dev_performance[dev] = {
            "completed_this_week": this_week,
            "completed_last_week": last_week,
            "trend": round(trend, 1),
            "reopened": reopened,
            "quality_issues": quality_issues
        }

    # Calculate team totals
    team_completed = sum(completed_by_dev.values())
    team_last_week = sum(last_week_by_dev.values())
    team_trend = ((team_completed - team_last_week) / team_last_week * 100) if team_last_week > 0 else 0

    return {
        "week_of": this_week_start.strftime("%B %d, %Y"),
        "developer_performance": dev_performance,
        "team_totals": {
            "completed": team_completed,
            "last_week": team_last_week,
            "trend": round(team_trend, 1),
            "reopened": total_reopens_this_week,
            "reopened_last_week": total_reopens_last_week
        },
        "expedite_tickets": expedites,
        "date": datetime.utcnow().strftime("%B %d, %Y")
    }


if __name__ == "__main__":
    # Test metrics calculations
    print("Reopen Rates (30 days):")
    print(calculate_reopen_rate())
    print("\nTime in Status (30 days):")
    print(calculate_time_in_status())
    print("\nVelocity:")
    print(calculate_velocity())
    print("\nStale Tickets:")
    print(get_stale_tickets())
