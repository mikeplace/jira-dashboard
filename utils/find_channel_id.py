"""
Utility to find the Slack channel ID for a given channel name.
Run this after setting up your Slack bot token.

Usage:
    python utils/find_channel_id.py ongoing-sprint-work
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import config


def find_channel_id(channel_name: str) -> str:
    """Find the channel ID for a given channel name."""
    if not config.SLACK_BOT_TOKEN:
        print("Error: SLACK_BOT_TOKEN not set in .env file")
        return None

    # Remove # if present
    channel_name = channel_name.lstrip('#')

    headers = {
        "Authorization": f"Bearer {config.SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    # List public channels
    response = requests.get(
        "https://slack.com/api/conversations.list",
        headers=headers,
        params={"types": "public_channel,private_channel", "limit": 500}
    )

    data = response.json()

    if not data.get("ok"):
        print(f"Error from Slack API: {data.get('error')}")
        if data.get("error") == "missing_scope":
            print("\nYour bot needs the 'channels:read' scope.")
            print("Go to api.slack.com/apps → Your App → OAuth & Permissions → Add scope")
        return None

    channels = data.get("channels", [])

    for channel in channels:
        if channel["name"] == channel_name:
            channel_id = channel["id"]
            print(f"\nFound channel '{channel_name}'!")
            print(f"Channel ID: {channel_id}")
            print(f"\nAdd this to your .env file:")
            print(f"SLACK_STANDUP_CHANNEL_ID={channel_id}")
            return channel_id

    print(f"\nChannel '{channel_name}' not found.")
    print("Make sure:")
    print("  1. The channel exists and is not archived")
    print("  2. Your bot has been added to the channel")
    print("  3. For private channels, bot needs 'groups:read' scope")

    print("\nAvailable channels your bot can see:")
    for ch in channels[:20]:
        print(f"  - #{ch['name']} ({ch['id']})")

    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        channel = config.SLACK_STANDUP_CHANNEL or "ongoing-sprint-work"
    else:
        channel = sys.argv[1]

    find_channel_id(channel)
