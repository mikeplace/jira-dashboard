"""
Flask web dashboard for team performance metrics.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, jsonify, request
from pathlib import Path
import subprocess
import json
from datetime import datetime
import config
import metrics
import db

app = Flask(__name__)

# File to store latest AI insights
AI_INSIGHTS_FILE = Path(__file__).parent.parent / "latest_ai_insights.json"


@app.route("/")
def index():
    """Main dashboard page."""
    return render_template("index.html",
                          jira_url=config.JIRA_URL,
                          project_key=config.JIRA_PROJECT_KEY,
                          github_enabled=config.GITHUB_ENABLED)


@app.route("/api/summary")
def api_summary():
    """API endpoint for dashboard data."""
    try:
        summary = metrics.get_dashboard_summary()
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reopen-rates")
def api_reopen_rates():
    """API endpoint for reopen rates."""
    days = int(os.environ.get("DAYS", 30))
    return jsonify(metrics.calculate_reopen_rate(days))


@app.route("/api/time-in-status")
def api_time_in_status():
    """API endpoint for time in status metrics."""
    days = int(os.environ.get("DAYS", 30))
    return jsonify(metrics.calculate_time_in_status(days))


@app.route("/api/velocity")
def api_velocity():
    """API endpoint for velocity data."""
    return jsonify(metrics.calculate_velocity())


@app.route("/api/stale-tickets")
def api_stale_tickets():
    """API endpoint for stale tickets."""
    return jsonify(metrics.get_stale_tickets())


@app.route("/api/tickets")
def api_tickets():
    """API endpoint for all tickets."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM tickets
        ORDER BY updated_at DESC
        LIMIT 100
    """)
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])


@app.route("/api/ai-insights")
def api_ai_insights():
    """Get the latest AI insights."""
    try:
        if AI_INSIGHTS_FILE.exists():
            with open(AI_INSIGHTS_FILE) as f:
                data = json.load(f)
            return jsonify(data)
        else:
            return jsonify({
                "insights": None,
                "generated_at": None,
                "message": "No AI analysis yet. Run 'python main.py daily-ai' to generate."
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai-insights/generate", methods=["POST"])
def api_generate_ai_insights():
    """Trigger a new AI analysis using Claude Code."""
    try:
        # Generate the metrics report
        data = metrics.get_daily_digest_data()

        # Format report for Claude
        report_lines = [f"=== TEAM PERFORMANCE REPORT - {data['date']} ===\n"]
        report_lines.append(f"VELOCITY: {data['velocity']['this_week']} this week, {data['velocity']['last_week']} last week ({data['velocity']['trend']:+.1f}%)")
        report_lines.append(f"\nREOPENED YESTERDAY ({len(data['reopened_yesterday'])}):")
        for t in data['reopened_yesterday'][:5]:
            report_lines.append(f"  - {t['ticket_key']}: {t['summary'][:50]} ({t['assignee']})")

        report_lines.append(f"\nSTALE TICKETS ({len(data['stale_tickets'])}):")
        for t in data['stale_tickets'][:5]:
            report_lines.append(f"  - {t['ticket_key']}: {t['status']} for {t['days_stale']}d ({t['assignee']})")

        report_lines.append("\nREOPEN RATES:")
        for name, stats in sorted(data['reopen_rates'].items(), key=lambda x: -x[1]['rate']):
            report_lines.append(f"  - {name}: {stats['rate']}% ({stats['reopened']}/{stats['total']})")

        report_content = "\n".join(report_lines)

        prompt = f"""You are a delivery lead assistant analyzing team performance.

Provide a brief assessment (3-5 bullet points) covering:
1. Risk flags or blockers needing attention
2. Team performance patterns (who might need support, quality trends)
3. One specific actionable recommendation

Be direct and specific. Reference ticket numbers and names when relevant.

Data:
{report_content}"""

        # Call Claude Code
        result = subprocess.run(
            ["claude", "-p", prompt, "--print"],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0 and result.stdout.strip():
            insights = result.stdout.strip()

            # Save to file
            with open(AI_INSIGHTS_FILE, 'w') as f:
                json.dump({
                    "insights": insights,
                    "generated_at": datetime.utcnow().isoformat()
                }, f)

            return jsonify({
                "insights": insights,
                "generated_at": datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                "error": "Claude Code returned no output",
                "stderr": result.stderr
            }), 500

    except FileNotFoundError:
        return jsonify({
            "error": "Claude Code not installed",
            "message": "Install with: npm install -g @anthropic-ai/claude-code"
        }), 500
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Claude Code timed out"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def run_server():
    """Run the Flask development server."""
    db.init_db()
    app.run(
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        debug=True
    )


def run_production():
    """Run the server with waitress (Windows-compatible)."""
    from waitress import serve
    db.init_db()
    print(f"Starting dashboard on http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}")
    serve(app, host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--production":
        run_production()
    else:
        run_server()
