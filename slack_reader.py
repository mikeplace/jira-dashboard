"""
Slack message reader for analyzing developer daily updates.
Compares stated plans with actual Jira activity.
"""

import requests
import re
from datetime import datetime, timedelta
from collections import defaultdict
import config
import db


class SlackReader:
    """Reads and analyzes messages from Slack channels."""

    def __init__(self):
        self.token = config.SLACK_BOT_TOKEN
        # Support multiple channels
        self.channel_ids = [
            config.SLACK_STANDUP_CHANNEL_ID,  # Main standup channel
            config.SLACK_VIPIN_CHANNEL_ID,     # Vipin's channel
        ]
        # Filter out empty channel IDs
        self.channel_ids = [c for c in self.channel_ids if c]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make an authenticated request to Slack API."""
        url = f"https://slack.com/api/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        data = response.json()

        if not data.get("ok"):
            print(f"Slack API error: {data.get('error')}")
            return None
        return data

    def get_channel_messages(self, hours: int = 24) -> list:
        """Fetch messages from all configured standup channels for the last N hours."""
        if not self.token or not self.channel_ids:
            print("Slack bot token or channel IDs not configured")
            return []

        oldest = (datetime.utcnow() - timedelta(hours=hours)).timestamp()
        all_messages = []

        for channel_id in self.channel_ids:
            data = self._make_request("conversations.history", {
                "channel": channel_id,
                "oldest": str(oldest),
                "limit": 200
            })

            if data:
                messages = data.get("messages", [])
                # Tag messages with channel source
                for msg in messages:
                    msg["_channel_id"] = channel_id
                all_messages.extend(messages)

        return all_messages

    def get_user_info(self, user_id: str) -> dict:
        """Get user info from Slack user ID."""
        data = self._make_request("users.info", {"user": user_id})
        if data:
            return data.get("user", {})
        return {}

    def parse_daily_updates(self, hours: int = 24) -> list:
        """
        Parse daily update messages and extract structured data.
        Returns list of updates with user, time, mentioned tickets, and stated work.
        """
        messages = self.get_channel_messages(hours)
        updates = []

        # Cache user lookups
        user_cache = {}

        for msg in messages:
            # Skip bot messages and thread replies
            if msg.get("bot_id") or msg.get("thread_ts"):
                continue

            user_id = msg.get("user")
            text = msg.get("text", "")
            timestamp = float(msg.get("ts", 0))

            # Get user name
            if user_id not in user_cache:
                user_info = self.get_user_info(user_id)
                user_cache[user_id] = user_info.get("real_name") or user_info.get("name", "Unknown")

            user_name = user_cache[user_id]

            # Extract ticket mentions (e.g., AEB-123)
            ticket_pattern = rf'{config.JIRA_PROJECT_KEY}-\d+'
            mentioned_tickets = re.findall(ticket_pattern, text, re.IGNORECASE)
            mentioned_tickets = [t.upper() for t in mentioned_tickets]

            # Determine if opening or closing update based on time
            msg_time = datetime.fromtimestamp(timestamp)
            is_opening = msg_time.hour < 12  # Before noon = opening

            # Extract key phrases
            working_on = []
            blockers = []
            completed = []

            text_lower = text.lower()

            # Look for "working on", "will work on", "focusing on", etc.
            work_patterns = [
                r'(?:working on|will work on|focusing on|starting|continuing)[:\s]+([^\n.]+)',
                r'(?:today|plan)[:\s]+([^\n]+)',
            ]
            for pattern in work_patterns:
                matches = re.findall(pattern, text_lower)
                working_on.extend(matches)

            # Look for blockers
            blocker_patterns = [
                r'(?:blocked|blocker|waiting on|stuck on)[:\s]+([^\n.]+)',
                r'(?:need help|need support)[:\s]+([^\n.]+)',
            ]
            for pattern in blocker_patterns:
                matches = re.findall(pattern, text_lower)
                blockers.extend(matches)

            # Look for completed items
            done_patterns = [
                r'(?:completed|finished|done|merged|deployed)[:\s]+([^\n.]+)',
                r'(?:yesterday|closed)[:\s]+([^\n.]+)',
            ]
            for pattern in done_patterns:
                matches = re.findall(pattern, text_lower)
                completed.extend(matches)

            updates.append({
                "user": user_name,
                "user_id": user_id,
                "timestamp": timestamp,
                "datetime": msg_time.isoformat(),
                "is_opening": is_opening,
                "update_type": "opening" if is_opening else "closing",
                "raw_text": text,
                "mentioned_tickets": mentioned_tickets,
                "working_on": working_on,
                "blockers": blockers,
                "completed": completed
            })

        return sorted(updates, key=lambda x: x["timestamp"], reverse=True)


def compare_updates_with_jira(hours: int = 48) -> dict:
    """
    Compare Slack daily updates with actual Jira activity.
    Returns analysis of discrepancies and patterns.
    """
    reader = SlackReader()
    updates = reader.parse_daily_updates(hours)

    if not updates:
        return {
            "available": False,
            "message": "No Slack updates found or Slack integration not configured"
        }

    # Get all mentioned tickets from updates
    all_mentioned_tickets = set()
    user_mentions = defaultdict(set)
    user_blockers = defaultdict(list)
    user_completed = defaultdict(list)

    for update in updates:
        user = update["user"]
        for ticket in update["mentioned_tickets"]:
            all_mentioned_tickets.add(ticket)
            user_mentions[user].add(ticket)

        user_blockers[user].extend(update["blockers"])
        user_completed[user].extend(update["completed"])

    # Get Jira activity for these tickets
    conn = db.get_connection()
    cursor = conn.cursor()

    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

    # Check which mentioned tickets actually moved
    tickets_with_activity = set()
    ticket_status = {}

    for ticket in all_mentioned_tickets:
        cursor.execute("""
            SELECT ticket_key, status, updated_at FROM tickets
            WHERE ticket_key = ?
        """, (ticket,))
        row = cursor.fetchone()
        if row:
            ticket_status[ticket] = {
                "status": row["status"],
                "updated_at": row["updated_at"]
            }
            # Check if updated recently
            if row["updated_at"] >= cutoff:
                tickets_with_activity.add(ticket)

        # Check for status transitions
        cursor.execute("""
            SELECT COUNT(*) as count FROM status_transitions
            WHERE ticket_key = ? AND transitioned_at >= ?
        """, (ticket, cutoff))
        if cursor.fetchone()["count"] > 0:
            tickets_with_activity.add(ticket)

    # Find tickets that moved but weren't mentioned
    cursor.execute("""
        SELECT DISTINCT ticket_key, assignee, status FROM tickets
        WHERE updated_at >= ?
        AND status != 'Done'
    """, (cutoff,))

    moved_but_not_mentioned = []
    for row in cursor.fetchall():
        if row["ticket_key"] not in all_mentioned_tickets:
            moved_but_not_mentioned.append({
                "ticket": row["ticket_key"],
                "assignee": row["assignee"],
                "status": row["status"]
            })

    conn.close()

    # Analyze discrepancies
    mentioned_but_no_movement = all_mentioned_tickets - tickets_with_activity

    # Build per-user analysis
    user_analysis = {}
    for user, tickets in user_mentions.items():
        stalled = [t for t in tickets if t in mentioned_but_no_movement]
        active = [t for t in tickets if t in tickets_with_activity]

        user_analysis[user] = {
            "mentioned_tickets": list(tickets),
            "tickets_with_activity": active,
            "tickets_no_movement": stalled,
            "mentioned_blockers": user_blockers.get(user, []),
            "claimed_completed": user_completed.get(user, [])
        }

    return {
        "available": True,
        "period_hours": hours,
        "total_updates": len(updates),
        "unique_users": len(user_mentions),
        "mentioned_tickets": list(all_mentioned_tickets),
        "tickets_with_actual_movement": list(tickets_with_activity),
        "mentioned_but_no_movement": list(mentioned_but_no_movement),
        "moved_but_not_mentioned": moved_but_not_mentioned[:10],  # Limit
        "user_analysis": user_analysis,
        "raw_updates": updates[:20]  # Last 20 updates for context
    }


def detect_repetitive_mentions(days: int = 5) -> dict:
    """
    Detect tickets mentioned repeatedly over multiple days without progress.
    This flags the "same thing day after day" pattern.
    """
    reader = SlackReader()
    updates = reader.parse_daily_updates(hours=days * 24)

    if not updates:
        return {"available": False, "repetitive_tickets": []}

    # Group mentions by date and ticket
    from collections import defaultdict
    ticket_by_date = defaultdict(set)  # {ticket: set of dates mentioned}
    ticket_users = defaultdict(set)     # {ticket: set of users who mentioned it}

    for update in updates:
        date_str = update["datetime"][:10]  # YYYY-MM-DD
        for ticket in update["mentioned_tickets"]:
            ticket_by_date[ticket].add(date_str)
            ticket_users[ticket].add(update["user"])

    # Find tickets mentioned on 3+ different days
    repetitive = []
    for ticket, dates in ticket_by_date.items():
        if len(dates) >= 3:
            # Check if ticket actually moved in Jira during this period
            conn = db.get_connection()
            cursor = conn.cursor()
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

            cursor.execute("""
                SELECT COUNT(*) as count FROM status_transitions
                WHERE ticket_key = ? AND transitioned_at >= ?
            """, (ticket, cutoff))
            transitions = cursor.fetchone()["count"]

            cursor.execute("""
                SELECT status FROM tickets WHERE ticket_key = ?
            """, (ticket,))
            row = cursor.fetchone()
            current_status = row["status"] if row else "Unknown"
            conn.close()

            if transitions == 0:  # No movement despite repeated mentions
                repetitive.append({
                    "ticket": ticket,
                    "days_mentioned": len(dates),
                    "dates": sorted(dates),
                    "mentioned_by": list(ticket_users[ticket]),
                    "current_status": current_status,
                    "transitions_in_period": transitions
                })

    # Sort by most repetitive
    repetitive.sort(key=lambda x: -x["days_mentioned"])

    return {
        "available": True,
        "period_days": days,
        "repetitive_tickets": repetitive
    }


def format_standup_analysis_for_claude() -> str:
    """Format the standup analysis as text for Claude to analyze."""
    analysis = compare_updates_with_jira(hours=48)

    if not analysis["available"]:
        return f"STANDUP ANALYSIS: {analysis['message']}"

    lines = ["=== STANDUP VS JIRA ANALYSIS (Last 48 Hours) ===\n"]

    lines.append(f"Total standup updates analyzed: {analysis['total_updates']}")
    lines.append(f"Team members who posted: {analysis['unique_users']}\n")

    # Discrepancies
    no_movement = analysis["mentioned_but_no_movement"]
    if no_movement:
        lines.append(f"TICKETS MENTIONED BUT NO JIRA MOVEMENT ({len(no_movement)}):")
        for ticket in no_movement:
            lines.append(f"  - {ticket}")
        lines.append("")

    not_mentioned = analysis["moved_but_not_mentioned"]
    if not_mentioned:
        lines.append(f"TICKETS MOVED BUT NOT MENTIONED IN STANDUPS ({len(not_mentioned)}):")
        for item in not_mentioned[:5]:
            lines.append(f"  - {item['ticket']} ({item['status']}) - {item['assignee']}")
        lines.append("")

    # Per-user breakdown
    lines.append("PER-DEVELOPER BREAKDOWN:")
    for user, data in analysis["user_analysis"].items():
        lines.append(f"\n  {user}:")
        lines.append(f"    Mentioned tickets: {', '.join(data['mentioned_tickets']) or 'None'}")
        if data["tickets_no_movement"]:
            lines.append(f"    NO MOVEMENT on: {', '.join(data['tickets_no_movement'])}")
        if data["mentioned_blockers"]:
            lines.append(f"    Mentioned blockers: {'; '.join(data['mentioned_blockers'][:2])}")
        if data["claimed_completed"]:
            lines.append(f"    Claimed completed: {'; '.join(data['claimed_completed'][:2])}")

    # Repetitive mentions analysis (same ticket mentioned 3+ days without progress)
    repetition = detect_repetitive_mentions(days=5)
    if repetition["available"] and repetition["repetitive_tickets"]:
        lines.append(f"\nREPETITIVE MENTIONS - SAME TICKETS WITHOUT PROGRESS ({len(repetition['repetitive_tickets'])}):")
        lines.append("(Tickets mentioned 3+ days in standups but no Jira status change)")
        for item in repetition["repetitive_tickets"][:8]:
            lines.append(f"  - {item['ticket']}: mentioned {item['days_mentioned']} days, status still '{item['current_status']}'")
            lines.append(f"    Mentioned by: {', '.join(item['mentioned_by'])}")
        lines.append("")

    # Recent raw updates for context
    lines.append("\n\nRECENT STANDUP MESSAGES (for context):")
    for update in analysis["raw_updates"][:10]:
        lines.append(f"\n  [{update['update_type'].upper()}] {update['user']} ({update['datetime'][:16]}):")
        # Truncate long messages
        text = update["raw_text"][:300]
        if len(update["raw_text"]) > 300:
            text += "..."
        lines.append(f"    {text}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test the analysis
    print(format_standup_analysis_for_claude())
