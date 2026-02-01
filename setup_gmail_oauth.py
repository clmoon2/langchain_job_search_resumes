#!/usr/bin/env python3
"""
Gmail OAuth2 Setup Script
=========================
Run this ONCE on a machine with a browser to get OAuth2 credentials.
After running, add the refresh token to your .env file.

SETUP STEPS:
1. Go to Google Cloud Console: https://console.cloud.google.com/
2. Create a new project or select existing
3. Enable Gmail API: APIs & Services > Library > Gmail API
4. Create OAuth 2.0 credentials:
   - APIs & Services > Credentials > Create Credentials > OAuth client ID
   - Application type: Desktop app
   - Download the JSON file
5. Rename the JSON file to 'gmail_credentials.json' in this directory
6. Run this script: python setup_gmail_oauth.py
7. Copy the output tokens to your .env file
"""

import os
import json
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import click

# Configuration
CREDENTIALS_FILE = "gmail_credentials.json"
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',      # Send emails
    'https://www.googleapis.com/auth/gmail.readonly',  # Check for replies
]


def main():
    print("=" * 60)
    print("Gmail OAuth2 Setup")
    print("=" * 60)

    # Check for credentials file
    if not Path(CREDENTIALS_FILE).exists():
        click.secho(f"\n[ERROR] {CREDENTIALS_FILE} not found!", fg="red")
        print("\nTo set up Gmail OAuth2:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create/select a project")
        print("3. Enable Gmail API")
        print("4. Create OAuth 2.0 credentials (Desktop app)")
        print("5. Download the JSON and rename to 'gmail_credentials.json'")
        print("6. Run this script again")
        return

    click.secho(f"\n[OK] Found {CREDENTIALS_FILE}", fg="green")
    print("Starting OAuth2 flow...\n")
    print("A browser window will open. Sign in with your Gmail account and grant access.\n")

    # Run OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=8080)

    # Extract tokens
    print("\n" + "=" * 60)
    click.secho("[OK] Authentication successful!", fg="green")
    print("=" * 60)

    # Read client ID and secret from credentials file
    with open(CREDENTIALS_FILE, 'r') as f:
        client_config = json.load(f)

    installed = client_config.get('installed', client_config.get('web', {}))
    client_id = installed.get('client_id', '')
    client_secret = installed.get('client_secret', '')

    print("\nAdd these to your .env file:")
    print("-" * 60)
    print(f"GMAIL_CLIENT_ID={client_id}")
    print(f"GMAIL_CLIENT_SECRET={client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
    print("-" * 60)

    # Also save to a file for reference
    output_file = "gmail_tokens.txt"
    with open(output_file, 'w') as f:
        f.write("# Gmail OAuth2 Tokens\n")
        f.write("# Add these to your .env file\n\n")
        f.write(f"GMAIL_CLIENT_ID={client_id}\n")
        f.write(f"GMAIL_CLIENT_SECRET={client_secret}\n")
        f.write(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}\n")

    print(f"\nTokens also saved to {output_file}")
    click.secho("\n[WARN] Keep these tokens secure! Do not commit them to git.", fg="yellow")

    # Update .env_example.md
    print("\nRecommended .env additions:")
    print("""
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
GMAIL_REFRESH_TOKEN=your_refresh_token
SENDER_EMAIL=carlunpen@gmail.com
""")


if __name__ == "__main__":
    main()
