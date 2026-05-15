"""
Database layer for storing ticket metrics historically.
Uses SQLite for simplicity and portability.
"""

import sqlite3
from datetime import datetime
from typing import Optional
import config


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_connection()
    cursor = conn.cursor()

    # Tickets table - stores current state of each ticket
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_key TEXT PRIMARY KEY,
            summary TEXT,
            assignee TEXT,
            status TEXT,
            priority TEXT,
            labels TEXT,
            created_at TEXT,
            updated_at TEXT,
            resolved_at TEXT,
            reopen_count INTEGER DEFAULT 0,
            last_synced_at TEXT
        )
    """)

    # Status transitions - tracks every status change for time-in-status calculations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS status_transitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_key TEXT,
            from_status TEXT,
            to_status TEXT,
            transitioned_at TEXT,
            transitioned_by TEXT,
            FOREIGN KEY (ticket_key) REFERENCES tickets(ticket_key)
        )
    """)

    # Daily snapshots - aggregated metrics per day for trend charts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT,
            assignee TEXT,
            tickets_completed INTEGER DEFAULT 0,
            tickets_reopened INTEGER DEFAULT 0,
            avg_cycle_time_hours REAL,
            UNIQUE(snapshot_date, assignee)
        )
    """)

    # Pull requests (optional GitHub integration)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pull_requests (
            pr_number INTEGER PRIMARY KEY,
            title TEXT,
            author TEXT,
            state TEXT,
            created_at TEXT,
            merged_at TEXT,
            linked_ticket TEXT,
            last_synced_at TEXT
        )
    """)

    # Create indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_assignee ON tickets(assignee)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transitions_ticket ON status_transitions(ticket_key)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transitions_date ON status_transitions(transitioned_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_date ON daily_snapshots(snapshot_date)")

    conn.commit()
    conn.close()
    print("Database initialized successfully.")


def upsert_ticket(ticket_key: str, summary: str, assignee: str, status: str,
                  created_at: str, updated_at: str, resolved_at: Optional[str] = None,
                  reopen_count: int = 0, priority: str = None, labels: str = None):
    """Insert or update a ticket record."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tickets (ticket_key, summary, assignee, status, priority, labels,
                            created_at, updated_at, resolved_at, reopen_count, last_synced_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticket_key) DO UPDATE SET
            summary = excluded.summary,
            assignee = excluded.assignee,
            status = excluded.status,
            priority = excluded.priority,
            labels = excluded.labels,
            updated_at = excluded.updated_at,
            resolved_at = excluded.resolved_at,
            reopen_count = excluded.reopen_count,
            last_synced_at = excluded.last_synced_at
    """, (ticket_key, summary, assignee, status, priority, labels, created_at, updated_at,
          resolved_at, reopen_count, datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()


def insert_status_transition(ticket_key: str, from_status: str, to_status: str,
                             transitioned_at: str, transitioned_by: str):
    """Record a status transition (avoids duplicates)."""
    conn = get_connection()
    cursor = conn.cursor()

    # Check if this transition already exists
    cursor.execute("""
        SELECT id FROM status_transitions
        WHERE ticket_key = ? AND from_status = ? AND to_status = ? AND transitioned_at = ?
    """, (ticket_key, from_status, to_status, transitioned_at))

    if cursor.fetchone() is None:
        cursor.execute("""
            INSERT INTO status_transitions (ticket_key, from_status, to_status,
                                           transitioned_at, transitioned_by)
            VALUES (?, ?, ?, ?, ?)
        """, (ticket_key, from_status, to_status, transitioned_at, transitioned_by))
        conn.commit()

    conn.close()


def save_daily_snapshot(snapshot_date: str, assignee: str, tickets_completed: int,
                        tickets_reopened: int, avg_cycle_time_hours: Optional[float] = None):
    """Save or update daily metrics snapshot."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO daily_snapshots (snapshot_date, assignee, tickets_completed,
                                     tickets_reopened, avg_cycle_time_hours)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_date, assignee) DO UPDATE SET
            tickets_completed = excluded.tickets_completed,
            tickets_reopened = excluded.tickets_reopened,
            avg_cycle_time_hours = excluded.avg_cycle_time_hours
    """, (snapshot_date, assignee, tickets_completed, tickets_reopened, avg_cycle_time_hours))

    conn.commit()
    conn.close()


def get_tickets_by_status(status: str) -> list:
    """Get all tickets in a given status."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets WHERE status = ?", (status,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_tickets_by_assignee(assignee: str) -> list:
    """Get all tickets assigned to a person."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets WHERE assignee = ?", (assignee,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_status_transitions(ticket_key: str) -> list:
    """Get all status transitions for a ticket, ordered by time."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM status_transitions
        WHERE ticket_key = ?
        ORDER BY transitioned_at ASC
    """, (ticket_key,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_all_transitions_since(since_date: str) -> list:
    """Get all status transitions since a given date."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT st.*, t.assignee, t.summary
        FROM status_transitions st
        JOIN tickets t ON st.ticket_key = t.ticket_key
        WHERE st.transitioned_at >= ?
        ORDER BY st.transitioned_at DESC
    """, (since_date,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_daily_snapshots(days: int = 30) -> list:
    """Get daily snapshots for the last N days."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM daily_snapshots
        WHERE snapshot_date >= date('now', ?)
        ORDER BY snapshot_date ASC
    """, (f'-{days} days',))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_stale_tickets(threshold_days: int) -> list:
    """Get tickets that haven't been updated in threshold_days."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM tickets
        WHERE status NOT IN ('Done', 'Closed')
        AND updated_at < datetime('now', ?)
        ORDER BY updated_at ASC
    """, (f'-{threshold_days} days',))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    init_db()
