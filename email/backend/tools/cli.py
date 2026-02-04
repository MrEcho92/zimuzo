#!/usr/bin/env
"""
CLI Helper Tool
"""

import json
import os
import random
import string
import sys
from pathlib import Path

import requests

_RANDOM_ALUM = string.ascii_lowercase


API_URL = os.getenv("API_URL", "http://localhost:8000")


def random_string(characters=_RANDOM_ALUM, length=5):
    return "".join(random.choice(characters) for _ in range(length))


def make_request(method, endpoint, username=None, data=None, headers=None):
    """Make HTTP request"""
    url = f"{API_URL}{endpoint}"
    headers = {"X-API-Key": get_token(username)} if username else None
    try:
        if method == "GET":
            res = requests.get(url=url, headers=headers)
        elif method == "POST":
            res = requests.post(url=url, json=data, headers=headers)
        else:
            print(f"Unsupported method: {method}")
            return None

        if res.status_code in [200, 201]:
            return res.json()
        print(f"Error: {res.status_code}")
        print(res.text)
        return None
    except json.JSONDecodeError as e:
        print(f"Request Failed: {e}")
        return None


def init_db():
    """Initialize database"""
    print("🗄️  Initializing database...")
    print("Database tables are auto-created on first run")

    # Test connection
    result = make_request("GET", "/health")
    if result:
        print("Database initialized successfully")
        print(json.dumps(result, indent=2))
    else:
        print("Failed to initialize database")


def get_token(username):
    base_path = Path(__file__).resolve().parent
    api_keys_path = base_path / "tokens.json"
    if not api_keys_path.exists():
        return None

    try:
        with open(api_keys_path, "r") as f:
            data = json.load(f)
        return data.get(username)
    except json.JSONDecodeError:
        print("Error: tokens.json is corrupted or empty")
        return None
    except Exception as e:
        print(f"Error getting token: {e}")
        return None


def save_token(username, api_key):
    base_path = Path(__file__).resolve().parent
    api_keys_path = base_path / "tokens.json"

    if api_keys_path.exists():
        try:
            with open(api_keys_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error getting token: {e}")
            data = {}
    else:
        data = {}

    data[username] = api_key

    with open(api_keys_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Successfully saved API key for user: {username}")
    return True


def create_user_profile():
    username = f"test_user_{random_string()}"
    email = f"{username}@email.com"

    result = make_request(
        "POST",
        "/api/v1/admin/users/create",
        data={"username": username, "email": email},
    )

    if not result:
        print("Failed to create user profile")
        return
    # Generate token for user
    payload = make_request("POST", f"/api/v1/admin/users/{username}/keys/generate")
    if payload:
        api_key = payload["api_key"]
        save_token(username, api_key)
        print("Saved API key to file to tools/tokens.json")
    else:
        print("Failed to generate API key")


def create_inbox(username, name=None, system_prompt=None):
    name = name or f"inbox_{random_string()}"
    data = {"name": name}

    if system_prompt:
        data["system_prompt"] = system_prompt

    result = make_request(
        "POST",
        "/api/v1/inboxes/create",
        username=username,
        data=data,
    )
    if result:
        print("Inbox created successfully!")
        print(json.dumps(result, indent=2))
    else:
        print("Failed to create inbox")


def list_inboxes(username):
    """List inboxes"""
    result = make_request("GET", "/api/v1/inboxes", username=username)
    if result:
        print("Get Inboxes successfully!")
        print(json.dumps(result, indent=2))
    else:
        print("result", result)
        print("Failed to get inboxes")


def send_message(username, inbox_name, to_email):
    """Send message"""
    inboxes = make_request("GET", "/api/v1/inboxes", username=username)
    if not inboxes:
        print("Failed to get inboxes")
    print("inboxes", inboxes)
    inbox = [inbox for inbox in inboxes if inbox.get("name") == inbox_name]
    if not inbox:
        print(f"Inbox '{inbox_name}' not found")
        return
    inbox = inbox[0]

    data = {
        "inbox_id": inbox.get("id"),
        "to_address": to_email,
        "subject": "Test Email - Verification Code",
        "body_text": """Hello!

        This is a test email with a verification code.

        Your verification code is: 123456

        You can also verify by clicking this link:
        https://app.example.com/verify/abc123def456

        This code will expire in 10 minutes.

        Best regards,
        Zimuzo Agent API
        """,
    }

    result = make_request("POST", "/api/v1/messages", username, data)
    if result:
        print("Test email queued!")
        print(json.dumps(result, indent=2))
        print(f"   curl {API_URL}/api/v1/messages/{result['id']}")
    else:
        print("Failed to send test email")


def show_help():
    """Show help message"""
    print(
        """
            Email Agent API - CLI Helper Tool

            Commands:
                init-db                          Initialize database
                create-user-profile              Create test user profile
                create-inbox <name>              Create new inbox
                create-inbox <username> <name>   Create inbox
                list-inboxes <username>          List all inboxes
                send-test <inbox> <email>        Send test email
                health                           Health check

            Examples:
                python cli.py init-db
                python cli.py create-user-profile
                python cli.py create-inbox support
                python cli.py create-inbox <username> sales
                python cli.py send-message support customer@example.com
                python cli.py list-inboxes <username>
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
    elif command == "create-user-profile":
        create_user_profile()
    elif command == "create-inbox":
        if len(sys.argv) < 3:
            print("Usage: python cli.py create-inbox <username> <name>")
            return
        username = sys.argv[2]
        name = sys.argv[3] if len(sys.argv) > 3 else None
        create_inbox(username, name)
    elif command == "list-inboxes":
        if len(sys.argv) < 2:
            print("Usage: python cli.py list-inboxes <username>")
        username = sys.argv[2]
        list_inboxes(username)
    elif command == "send-message":
        if len(sys.argv) < 4:
            print("Usage: python cli.py send-test <username> <inbox_name> <to_email>")
            return
        username = sys.argv[2]
        inbox_name = sys.argv[3]
        to_email = sys.argv[4]
        send_message(username, inbox_name, to_email)
    else:
        print(f"Unknown command: {command}")
        show_help()


if __name__ == "__main__":
    main()
