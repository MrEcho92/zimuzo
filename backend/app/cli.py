#!/usr/bin/env
"""
CLI Helper Tool

Usage:
    python cli.py init-db          # Initialize database
    python cli.py create-inbox support  # Create inbox
    python cli.py send-test support customer@example.com  # Send test email
    python cli.py list-inboxes     # List all inboxes
    python cli.py stats            # Show statistics
"""

import sys
import os
import requests
import json

API_URL = os.getenv("API_URL", "http://localhost:8000/")


def make_request(method, endpoint, data=None):
    """Make HTTP request"""
    api_url = API_URL.lstrip("/")
    url = f"{api_url}{endpoint}"
    try:
        if method == "GET":
            res = requests.get(url=url)
        elif method == "POST":
            res = requests.post(url=url, json=data)
        else:
            print(f"Unsupported method: {method}")
            return None

        if res.status_code in [200, 201]:
            return res.json()
        print(f"Error: {res.status_code}")
        print(res.text)
        return None
    except Exception as e:
        print(f"Request Failed: {e}")
        return None


def init_db():
    """Initialize database"""
    print("🗄️  Initializing database...")
    print("Database tables are auto-created on first run")

    # Test connection
    result = make_request("GET", "/health")
    if result:
        print("✅ Database initialized successfully")
        print(json.dumps(result, indent=2))
    else:
        print("❌ Failed to initialize database")


def create_user_info():
    pass


def create_inbox(project_id, name, system_prompt=None):
    pass


def list_inboxes():
    pass


def show_help():
    """Show help message"""
    print(
        """
Email Agent API - CLI Helper Tool

Commands:
    init-db                          Initialize database
    create-inbox <name>              Create new inbox
    create-inbox <name> <webhook>    Create inbox with webhook
    list-inboxes                     List all inboxes
    send-test <inbox> <email>        Send test email
    stats                            Show statistics
    health                           Health check
    help                             Show this help

Examples:
    python cli.py init-db
    python cli.py create-inbox support
    python cli.py create-inbox sales https://myapp.com/webhooks
    python cli.py send-test support customer@example.com
    python cli.py list-inboxes
    python cli.py stats
    python cli.py health

Environment Variables:
    API_URL - API base URL (default: http://localhost:8000)
"""
    )


def main():
    if len(sys.argv) < 2:
        show_help()
        return

    command = sys.argv[1]
    if command == "init-db":
        init_db()


if __name__ == "__main__":
    main()
