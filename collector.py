"""
Data collector for Jira and GitHub.
Fetches tickets, parses changelogs, and stores in database.
"""

import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
from typing import Optional
import config
import db


class JiraCollector:
    """Collects ticket data from Jira Cloud."""

    def __init__(self):
        self.base_url = config.JIRA_URL.rstrip('/')
        self.auth = HTTPBasicAuth(config.JIRA_EMAIL, config.JIRA_API_TOKEN)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def search_tickets(self, jql: str, max_results: int = 100, next_page_token: str = None) -> dict:
        """Search for tickets using JQL (new API endpoint with cursor pagination)."""
        url = f"{self.base_url}/rest/api/3/search/jql"
        body = {
            "jql": jql,
            "maxResults": max_results,
            "fields": ["summary", "assignee", "status", "created", "updated", "resolutiondate", "priority", "labels"]
        }
        if next_page_token:
            body["nextPageToken"] = next_page_token
        response = requests.post(url, headers=self.headers, auth=self.auth, json=body)
        response.raise_for_status()
        return response.json()

    def get_issue_changelog(self, ticket_key: str) -> list:
        """Fetch changelog for a specific issue."""
        url = f"{self.base_url}/rest/api/3/issue/{ticket_key}/changelog"
        response = requests.get(url, headers=self.headers, auth=self.auth)
        if response.status_code == 200:
            return response.json().get("values", [])
        return []

    def get_all_project_tickets(self, updated_since_days: int = None) -> list:
        """Fetch all tickets from the project, optionally filtered by update date."""
        jql = f"project = {config.JIRA_PROJECT_KEY}"
        if updated_since_days:
            jql += f" AND updated >= -{updated_since_days}d"
        jql += " ORDER BY updated DESC"

        all_tickets = []
        next_page_token = None
        max_results = 100

        while True:
            result = self.search_tickets(jql, max_results, next_page_token)
            issues = result.get("issues", [])
            all_tickets.extend(issues)

            # Check if there are more pages
            if result.get("isLast", True):
                break
            next_page_token = result.get("nextPageToken")
            if not next_page_token:
                break

        print(f"Fetched {len(all_tickets)} tickets from Jira")
        return all_tickets

    def parse_changelog(self, changelog_values: list) -> tuple[list, int]:
        """
        Parse the changelog to extract status transitions.
        Returns (transitions_list, reopen_count)
        """
        transitions = []
        reopen_count = 0

        for history in changelog_values:
            created = history.get("created")
            author = history.get("author", {}).get("displayName", "Unknown")

            for item in history.get("items", []):
                if item.get("field") == "status":
                    from_status = item.get("fromString", "")
                    to_status = item.get("toString", "")

                    transitions.append({
                        "from_status": from_status,
                        "to_status": to_status,
                        "transitioned_at": created,
                        "transitioned_by": author
                    })

                    # Count reopens
                    if to_status == config.REOPEN_STATUS:
                        reopen_count += 1

        return transitions, reopen_count

    def sync_tickets(self, updated_since_days: int = None):
        """
        Sync tickets from Jira to local database.
        If updated_since_days is provided, only syncs recently updated tickets.
        """
        tickets = self.get_all_project_tickets(updated_since_days)

        for i, ticket in enumerate(tickets):
            ticket_key = ticket.get("key")
            fields = ticket.get("fields", {})

            # Extract assignee (handle unassigned tickets)
            assignee_data = fields.get("assignee")
            assignee = assignee_data.get("displayName") if assignee_data else "Unassigned"

            # Parse dates
            created_at = fields.get("created", "")
            updated_at = fields.get("updated", "")
            resolved_at = fields.get("resolutiondate")

            # Current status
            status = fields.get("status", {}).get("name", "Unknown")

            # Priority and labels
            priority_data = fields.get("priority")
            priority = priority_data.get("name") if priority_data else None
            labels = ",".join(fields.get("labels", []))

            # Fetch and parse changelog (separate API call)
            changelog_values = self.get_issue_changelog(ticket_key)
            transitions, reopen_count = self.parse_changelog(changelog_values)

            # Save ticket to database
            db.upsert_ticket(
                ticket_key=ticket_key,
                summary=fields.get("summary", ""),
                assignee=assignee,
                status=status,
                created_at=created_at,
                updated_at=updated_at,
                resolved_at=resolved_at,
                reopen_count=reopen_count,
                priority=priority,
                labels=labels
            )

            # Save status transitions
            for transition in transitions:
                db.insert_status_transition(
                    ticket_key=ticket_key,
                    from_status=transition["from_status"],
                    to_status=transition["to_status"],
                    transitioned_at=transition["transitioned_at"],
                    transitioned_by=transition["transitioned_by"]
                )

            # Progress indicator
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(tickets)} tickets...")

        print(f"Synced {len(tickets)} tickets to database")
        return len(tickets)


class GitHubCollector:
    """Collects PR data from GitHub (optional)."""

    def __init__(self):
        self.enabled = config.GITHUB_ENABLED
        if not self.enabled:
            return

        self.token = config.GITHUB_TOKEN
        self.org = config.GITHUB_ORG
        self.repo = config.GITHUB_REPO
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {self.token}"
        }

    def _make_request(self, endpoint: str) -> dict:
        """Make an authenticated request to GitHub API."""
        url = f"https://api.github.com/repos/{self.org}/{self.repo}/{endpoint}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_open_pull_requests(self) -> list:
        """Fetch all open pull requests."""
        if not self.enabled:
            return []

        prs = self._make_request("pulls?state=open")
        print(f"Fetched {len(prs)} open PRs from GitHub")
        return prs

    def get_recent_pull_requests(self, days: int = 30) -> list:
        """Fetch PRs updated in the last N days."""
        if not self.enabled:
            return []

        all_prs = self._make_request("pulls?state=all&sort=updated&direction=desc&per_page=100")

        cutoff = datetime.utcnow() - timedelta(days=days)
        recent_prs = []

        for pr in all_prs:
            updated_at = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
            if updated_at.replace(tzinfo=None) >= cutoff:
                recent_prs.append(pr)

        print(f"Fetched {len(recent_prs)} recent PRs from GitHub")
        return recent_prs

    def extract_linked_ticket(self, pr: dict) -> Optional[str]:
        """
        Extract Jira ticket key from PR title or body.
        Looks for patterns like AEB-123.
        """
        import re
        pattern = rf'{config.JIRA_PROJECT_KEY}-\d+'

        # Check title
        title = pr.get("title", "")
        match = re.search(pattern, title)
        if match:
            return match.group()

        # Check body
        body = pr.get("body", "") or ""
        match = re.search(pattern, body)
        if match:
            return match.group()

        return None

    def sync_pull_requests(self, days: int = 30):
        """Sync recent PRs to database."""
        if not self.enabled:
            print("GitHub integration is disabled")
            return 0

        prs = self.get_recent_pull_requests(days)

        conn = db.get_connection()
        cursor = conn.cursor()

        for pr in prs:
            linked_ticket = self.extract_linked_ticket(pr)

            cursor.execute("""
                INSERT INTO pull_requests (pr_number, title, author, state, created_at,
                                          merged_at, linked_ticket, last_synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pr_number) DO UPDATE SET
                    title = excluded.title,
                    state = excluded.state,
                    merged_at = excluded.merged_at,
                    linked_ticket = excluded.linked_ticket,
                    last_synced_at = excluded.last_synced_at
            """, (
                pr["number"],
                pr["title"],
                pr["user"]["login"],
                pr["state"],
                pr["created_at"],
                pr.get("merged_at"),
                linked_ticket,
                datetime.utcnow().isoformat()
            ))

        conn.commit()
        conn.close()

        print(f"Synced {len(prs)} PRs to database")
        return len(prs)


def run_full_sync(updated_since_days: int = None):
    """Run a full sync of Jira (and optionally GitHub) data."""
    print(f"Starting sync at {datetime.now().isoformat()}")

    # Initialize database if needed
    db.init_db()

    # Sync Jira
    jira = JiraCollector()
    jira.sync_tickets(updated_since_days)

    # Sync GitHub (if enabled)
    github = GitHubCollector()
    github.sync_pull_requests()

    print("Sync complete!")


if __name__ == "__main__":
    # Run incremental sync (last 7 days) by default
    # Use run_full_sync() without arguments for full historical sync
    run_full_sync(updated_since_days=7)
