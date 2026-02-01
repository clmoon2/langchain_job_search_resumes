#!/usr/bin/env python3
"""
Script to add new column headers to the Google Sheet for email outreach.
Run once to set up the spreadsheet schema.
"""

import os
import json
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

# Configuration
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID", "")
SERVICE_ACCOUNT_SOURCE = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "service-account.json")

# New headers to add for email outreach + follow-up tracking
NEW_HEADERS = [
    "CompanyName",
    "JobTitle",
    "JobLocation",
    "PostedAt",
    "MatchedSkills",
    "EmailStatus",
    "EmailSentAt",
    "DraftedEmail",
    # Follow-up tracking fields
    "EmailCount",        # Number of emails sent (0, 1, 2, or 3)
    "LastEmailSentAt",   # Timestamp of most recent email
    "NextFollowUpDate",  # When to send next follow-up
]

def make_credentials(scopes):
    """Create service account credentials."""
    source = SERVICE_ACCOUNT_SOURCE
    if os.path.isfile(source):
        with open(source, "r", encoding="utf-8") as f:
            raw_json = f.read()
    else:
        raw_json = source
    info = json.loads(raw_json)
    return service_account.Credentials.from_service_account_info(info, scopes=scopes)

def get_current_headers(service, spreadsheet_id, sheet_name="Sheet1"):
    """Get existing headers from row 1."""
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!1:1"
    ).execute()
    values = result.get('values', [])
    return values[0] if values else []

def add_headers(service, spreadsheet_id, current_headers, new_headers, sheet_name="Sheet1"):
    """Add new headers to the end of row 1."""
    # Filter out headers that already exist
    headers_to_add = [h for h in new_headers if h not in current_headers]

    if not headers_to_add:
        print("All headers already exist. Nothing to add.")
        return

    # Calculate starting column (after existing headers)
    start_col = len(current_headers) + 1
    start_col_letter = chr(ord('A') + len(current_headers)) if len(current_headers) < 26 else f"A{chr(ord('A') + len(current_headers) - 26)}"

    # For columns beyond Z, use AA, AB, etc.
    if len(current_headers) >= 26:
        first = len(current_headers) // 26
        second = len(current_headers) % 26
        if first == 0:
            start_col_letter = chr(ord('A') + second)
        else:
            start_col_letter = chr(ord('A') + first - 1) + chr(ord('A') + second)
    else:
        start_col_letter = chr(ord('A') + len(current_headers))

    # Update the header row
    range_name = f"{sheet_name}!{start_col_letter}1"
    body = {'values': [headers_to_add]}

    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()

    print(f"Added {len(headers_to_add)} new headers: {headers_to_add}")
    print(f"Updated cells: {result.get('updatedCells')}")

def main():
    print("=" * 60)
    print("Adding new headers to Google Sheet for Email Outreach")
    print("=" * 60)

    # Create credentials and service
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = make_credentials(scopes)
    service = build('sheets', 'v4', credentials=creds)

    # Get current headers
    print(f"\nSpreadsheet ID: {GOOGLE_SHEETS_ID}")
    current_headers = get_current_headers(service, GOOGLE_SHEETS_ID)
    print(f"\nCurrent headers ({len(current_headers)}):")
    for i, h in enumerate(current_headers, 1):
        print(f"  {i}. {h}")

    # Add new headers
    print(f"\nNew headers to add:")
    for h in NEW_HEADERS:
        status = "(already exists)" if h in current_headers else "(will add)"
        print(f"  - {h} {status}")

    print("\nUpdating spreadsheet...")
    add_headers(service, GOOGLE_SHEETS_ID, current_headers, NEW_HEADERS)

    # Show final state
    final_headers = get_current_headers(service, GOOGLE_SHEETS_ID)
    print(f"\nFinal headers ({len(final_headers)}):")
    for i, h in enumerate(final_headers, 1):
        print(f"  {i}. {h}")

    print("\n" + "=" * 60)
    print("Done! Spreadsheet is ready for email outreach data.")
    print("=" * 60)

if __name__ == "__main__":
    main()
