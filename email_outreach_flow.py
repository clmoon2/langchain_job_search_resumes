#!/usr/bin/env python3
"""
Email Outreach Flow with Follow-Up System
==========================================
Automated email outreach for job applications with:
- Initial outreach emails
- Automated follow-ups (max 3 emails per person, 3 days apart)
- Reply detection to stop follow-ups when contact responds
- Priority-based processing (follow-ups first, then new emails)

Schedule: Daily at 8:30am Chicago time via systemd timer or cron.

Run manually:
    .venv/bin/python email_outreach_flow.py

Or as systemd service (see /etc/systemd/system/email-outreach.*)
"""

import os
import json
import base64
import random
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from dotenv import load_dotenv
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from openai import OpenAI
import click

# Load environment variables
load_dotenv()


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class Config:
    GOOGLE_SHEETS_ID: str = os.getenv("GOOGLE_SHEETS_ID", "")
    GOOGLE_SERVICE_ACCOUNT_JSON: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "service-account.json")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Gmail OAuth2 tokens (from one-time setup)
    GMAIL_CLIENT_ID: str = os.getenv("GMAIL_CLIENT_ID", "")
    GMAIL_CLIENT_SECRET: str = os.getenv("GMAIL_CLIENT_SECRET", "")
    GMAIL_REFRESH_TOKEN: str = os.getenv("GMAIL_REFRESH_TOKEN", "")

    # Sender info
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "")
    SENDER_NAME: str = "Carlos Luna-Peña"

    # Rate limiting - high volume with spam avoidance
    DAILY_EMAIL_LIMIT: int = 350      # Target 250-400 emails/day
    MIN_DELAY_SECONDS: int = 30       # Minimum wait between emails
    MAX_DELAY_SECONDS: int = 90       # Maximum wait between emails

    # Follow-up settings
    FOLLOW_UP_DAYS: int = 3           # Days between emails
    MAX_EMAILS_PER_CONTACT: int = 3   # Maximum emails to send per person

config = Config()


# =============================================================================
# CANDIDATE PROFILE (for email personalization)
# =============================================================================

CANDIDATE_PROFILE = """
Carlos Luna-Peña
CS student at Texas A&M University (Major GPA: 3.62)
Email: carlunpen@gmail.com
GitHub: github.com/clmoon2
LinkedIn: linkedin.com/in/carlos-luna
Portfolio: applyeasy.tech

KEY EXPERIENCE:
- Technical Lead at AIPHRODITE: Led 6-person team building AI fashion advisor with LangChain/RAG, Next.js, FastAPI, PostgreSQL
- Founder of applyeasy.tech: Job automation SaaS with n8n, OpenAI, React Native, and automated email outreach
- Building carlosOS: Educational OS in C/C++ with custom bootloader, kernel, and shell
- Full-stack experience with React, Next.js, Node.js, TypeScript, Python, PostgreSQL, Docker, CI/CD

STRENGTHS:
- Full-stack web development (React, Next.js, Node.js, TypeScript)
- AI/ML integration (LangChain, OpenAI, RAG, embeddings)
- Automation and workflow orchestration (n8n, APIs)
- Systems programming (C, C++, Linux, OS development)
- Team leadership and Agile methodologies
"""


# =============================================================================
# GOOGLE SHEETS CLIENT
# =============================================================================

class GoogleSheetsClient:
    """Client for Google Sheets operations with follow-up support."""

    def __init__(self):
        source = config.GOOGLE_SERVICE_ACCOUNT_JSON
        if os.path.isfile(source):
            with open(source, "r", encoding="utf-8") as f:
                raw_json = f.read()
        else:
            raw_json = source
        info = json.loads(raw_json)
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        self.creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        self.service = build('sheets', 'v4', credentials=self.creds)

    def get_all_rows(self, spreadsheet_id: str, sheet_name: str = "Sheet1") -> List[Dict]:
        """Read all rows from sheet as list of dicts."""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A:Z"
            ).execute()

            values = result.get('values', [])
            if not values or len(values) < 2:
                return []

            headers = values[0]
            rows = []
            for i, row in enumerate(values[1:], start=2):
                row_dict = {"_row_number": i}
                for j, header in enumerate(headers):
                    row_dict[header] = row[j] if j < len(row) else ""
                rows.append(row_dict)
            return rows
        except HttpError as e:
            print(f"Error reading sheet: {e}")
            return []

    def get_pending_emails(self, spreadsheet_id: str) -> List[Dict]:
        """Get rows where EmailStatus is 'pending' and Email is not empty."""
        all_rows = self.get_all_rows(spreadsheet_id)
        pending = []
        for row in all_rows:
            email_status = row.get("EmailStatus", "").strip().lower()
            email = row.get("Email", "").strip()
            if email_status == "pending" and email:
                pending.append(row)
        return pending

    def get_followups_due(self, spreadsheet_id: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Get rows where follow-up is due.
        Returns (followup_1_due, followup_2_due) sorted by priority.
        """
        all_rows = self.get_all_rows(spreadsheet_id)
        today = datetime.now().date()

        followup_1 = []  # EmailStatus = "sent", EmailCount = 1, 3+ days ago
        followup_2 = []  # EmailStatus = "followed_up_1", EmailCount = 2, 3+ days ago

        for row in all_rows:
            email_status = row.get("EmailStatus", "").strip().lower()
            email = row.get("Email", "").strip()
            email_count = int(row.get("EmailCount", "0") or "0")
            last_sent = row.get("LastEmailSentAt", "").strip()

            if not email or not last_sent:
                continue

            # Parse last sent date
            try:
                last_sent_date = datetime.strptime(last_sent[:10], "%Y-%m-%d").date()
                days_since = (today - last_sent_date).days
            except ValueError:
                continue

            # Check if follow-up is due (3+ days since last email)
            if days_since >= config.FOLLOW_UP_DAYS:
                if email_status == "sent" and email_count == 1:
                    followup_1.append(row)
                elif email_status == "followed_up_1" and email_count == 2:
                    followup_2.append(row)

        return followup_1, followup_2

    def update_row(self, spreadsheet_id: str, row_number: int, updates: Dict[str, str], sheet_name: str = "Sheet1"):
        """Update specific cells in a row."""
        try:
            # Get headers to find column indices
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!1:1"
            ).execute()
            headers = result.get('values', [[]])[0]

            # Build update requests
            for field, value in updates.items():
                if field in headers:
                    col_index = headers.index(field)
                    col_letter = self._col_to_letter(col_index)
                    range_name = f"{sheet_name}!{col_letter}{row_number}"
                    self.service.spreadsheets().values().update(
                        spreadsheetId=spreadsheet_id,
                        range=range_name,
                        valueInputOption='RAW',
                        body={'values': [[value]]}
                    ).execute()

        except HttpError as e:
            print(f"Error updating row {row_number}: {e}")

    def _col_to_letter(self, col_index: int) -> str:
        """Convert column index to letter (0=A, 25=Z, 26=AA, etc.)"""
        if col_index < 26:
            return chr(ord('A') + col_index)
        else:
            first = col_index // 26 - 1
            second = col_index % 26
            return chr(ord('A') + first) + chr(ord('A') + second)


# =============================================================================
# EMAIL GENERATOR (OpenAI)
# =============================================================================

class EmailGenerator:
    """Generate personalized outreach emails using OpenAI."""

    def __init__(self):
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)

    def generate_initial_email(self, job_data: Dict) -> Dict[str, str]:
        """Generate first contact email with resume link."""
        recipient_name = job_data.get("Name", "Hiring Manager")
        company_name = job_data.get("CompanyName", "your company")
        job_title = job_data.get("JobTitle", "the open position")
        matched_skills = job_data.get("MatchedSkills", "")
        job_description = job_data.get("JobDescription", "")[:2000]
        resume_url = job_data.get("ResumePdfUrl", "")

        prompt = f"""Write a cold outreach email for a CS student seeking an internship.

CANDIDATE PROFILE:
{CANDIDATE_PROFILE}

JOB DETAILS:
- Recipient: {recipient_name}
- Company: {company_name}
- Position: {job_title}
- Matched Skills: {matched_skills}
- Resume Link: {resume_url}
- Job Description (excerpt): {job_description[:1000]}

INSTRUCTIONS:
1. Write a SHORT, direct, professional email (under 150 words)
2. Use recipient's first name if available, otherwise "Hi there"
3. Mention the specific job title and company
4. Highlight 2-3 relevant skills from matched skills
5. Include the resume link naturally in the email
6. End with clear call to action (brief call or conversation)
7. Be confident but not arrogant
8. NO emojis, NO exclamation marks

OUTPUT FORMAT (JSON):
{{"subject": "...", "body": "..."}}
"""

        return self._generate(prompt, job_title, company_name, recipient_name)

    def generate_followup_1(self, job_data: Dict, original_subject: str) -> Dict[str, str]:
        """Generate first follow-up email (gentle bump)."""
        recipient_name = job_data.get("Name", "Hiring Manager")
        company_name = job_data.get("CompanyName", "your company")
        job_title = job_data.get("JobTitle", "the open position")
        matched_skills = job_data.get("MatchedSkills", "")
        job_description = job_data.get("JobDescription", "")[:1500]

        prompt = f"""Write a follow-up email for a previous outreach about an internship.

CONTEXT:
- This is follow-up #1 (sent 3 days after initial email)
- They haven't responded yet
- Original subject was: "{original_subject}"

CANDIDATE: Carlos Luna-Peña, CS student at Texas A&M (3.62 GPA)

JOB DETAILS:
- Recipient: {recipient_name}
- Company: {company_name}
- Position: {job_title}
- Matched Skills: {matched_skills}
- Job Description (excerpt): {job_description[:800]}

INSTRUCTIONS:
1. Keep it SHORT (under 100 words)
2. Reference the original email naturally
3. Add new value - mention something specific from job description
4. Connect your experience to their needs
5. Use subject "Re: {original_subject}" to thread the conversation
6. Be helpful, not pushy
7. NO emojis, NO exclamation marks

OUTPUT FORMAT (JSON):
{{"subject": "Re: {original_subject}", "body": "..."}}
"""

        return self._generate(prompt, job_title, company_name, recipient_name, f"Re: {original_subject}")

    def generate_followup_2(self, job_data: Dict, original_subject: str) -> Dict[str, str]:
        """Generate final follow-up email (last attempt, keep door open)."""
        recipient_name = job_data.get("Name", "Hiring Manager")
        company_name = job_data.get("CompanyName", "your company")
        job_title = job_data.get("JobTitle", "the open position")

        prompt = f"""Write a final follow-up email for an internship inquiry.

CONTEXT:
- This is follow-up #2 (final attempt, 6 days after initial email)
- They haven't responded to 2 previous emails
- Original subject was: "{original_subject}"

CANDIDATE: Carlos Luna-Peña, CS student at Texas A&M

JOB DETAILS:
- Recipient: {recipient_name}
- Company: {company_name}
- Position: {job_title}

INSTRUCTIONS:
1. Very SHORT (under 75 words)
2. Acknowledge this is last follow-up
3. Keep door open for future opportunities
4. Offer LinkedIn connection: linkedin.com/in/carlos-luna
5. Be gracious, not desperate
6. Use subject "Re: {original_subject}"
7. NO emojis, NO exclamation marks

OUTPUT FORMAT (JSON):
{{"subject": "Re: {original_subject}", "body": "..."}}
"""

        return self._generate(prompt, job_title, company_name, recipient_name, f"Re: {original_subject}")

    def _generate(self, prompt: str, job_title: str, company_name: str,
                  recipient_name: str, fallback_subject: str = None) -> Dict[str, str]:
        """Generate email using OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON from response
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content)
            return {
                "subject": result.get("subject", fallback_subject or f"Interest in {job_title} at {company_name}"),
                "body": result.get("body", "")
            }

        except Exception as e:
            click.secho(f"   [WARN] Error generating email: {e}", fg="yellow")
            first_name = recipient_name.split()[0] if recipient_name and recipient_name != "Hiring Manager" else "there"
            return {
                "subject": fallback_subject or f"CS Intern - {job_title} at {company_name}",
                "body": f"""Hi {first_name},

I'm Carlos Luna-Peña, a CS student at Texas A&M interested in the {job_title} role at {company_name}.

Would you be open to a brief conversation about the role?

Best,
Carlos
carlunpen@gmail.com | github.com/clmoon2
"""
            }


# =============================================================================
# GMAIL SENDER (OAuth2) with Reply Detection
# =============================================================================

class GmailSender:
    """Send emails via Gmail API with reply detection."""

    def __init__(self):
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Gmail using OAuth2 refresh token."""
        if not all([config.GMAIL_CLIENT_ID, config.GMAIL_CLIENT_SECRET, config.GMAIL_REFRESH_TOKEN]):
            click.secho("[WARN] Gmail OAuth credentials not configured. Run setup_gmail_oauth.py first.", fg="yellow")
            return

        try:
            creds = Credentials(
                token=None,
                refresh_token=config.GMAIL_REFRESH_TOKEN,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=config.GMAIL_CLIENT_ID,
                client_secret=config.GMAIL_CLIENT_SECRET,
                scopes=[
                    'https://www.googleapis.com/auth/gmail.send',
                    'https://www.googleapis.com/auth/gmail.readonly'
                ]
            )

            # Refresh the token
            creds.refresh(Request())

            self.service = build('gmail', 'v1', credentials=creds)
            click.secho("[OK] Gmail authenticated successfully", fg="green")

        except Exception as e:
            click.secho(f"[ERROR] Gmail authentication failed: {e}", fg="red")
            self.service = None

    def check_for_reply(self, recipient_email: str, since_date: str) -> bool:
        """
        Check if we received a reply from this email address.

        Args:
            recipient_email: Email address to check for replies from
            since_date: Date string (YYYY-MM-DD) to search from

        Returns:
            True if reply found, False otherwise
        """
        if not self.service:
            return False

        try:
            # Search for messages from this email after the date we sent
            query = f"from:{recipient_email} after:{since_date.replace('-', '/')}"
            results = self.service.users().messages().list(
                userId='me', q=query, maxResults=1
            ).execute()

            messages = results.get('messages', [])
            return len(messages) > 0

        except HttpError as e:
            click.secho(f"   [WARN] Error checking for reply from {recipient_email}: {e}", fg="yellow")
            return False

    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email via Gmail API."""
        if not self.service:
            click.secho("[ERROR] Gmail service not available", fg="red")
            return False

        try:
            message = MIMEMultipart()
            message['to'] = to
            message['from'] = f"{config.SENDER_NAME} <{config.SENDER_EMAIL}>"
            message['subject'] = subject

            # Add body
            message.attach(MIMEText(body, 'plain'))

            # Encode and send
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

            self.service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()

            return True

        except HttpError as e:
            click.secho(f"[ERROR] Error sending email to {to}: {e}", fg="red")
            return False


# =============================================================================
# MAIN OUTREACH FLOW
# =============================================================================

def run_outreach_flow():
    """Main email outreach flow with follow-up support."""
    print("=" * 70)
    print(f"EMAIL OUTREACH FLOW - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Initialize clients
    sheets = GoogleSheetsClient()
    email_gen = EmailGenerator()
    gmail = GmailSender()

    if not gmail.service:
        click.secho("\n[ERROR] Gmail not configured. Please run setup_gmail_oauth.py first.", fg="red")
        return

    # =========================================================================
    # PHASE 1: Check for replies and update statuses
    # =========================================================================
    print("\n[1/3] Checking for replies...")

    all_rows = sheets.get_all_rows(config.GOOGLE_SHEETS_ID)
    replied_count = 0

    for row in all_rows:
        email_status = row.get("EmailStatus", "").strip().lower()
        recipient_email = row.get("Email", "").strip()
        last_sent = row.get("LastEmailSentAt", "").strip()
        row_number = row.get("_row_number", 0)

        # Only check active conversations (sent, followed_up_1, followed_up_2)
        if email_status in ["sent", "followed_up_1", "followed_up_2"] and recipient_email and last_sent:
            since_date = last_sent[:10]  # YYYY-MM-DD
            if gmail.check_for_reply(recipient_email, since_date):
                click.secho(f"   [OK] Reply detected from {recipient_email}", fg="green")
                sheets.update_row(config.GOOGLE_SHEETS_ID, row_number, {
                    "EmailStatus": "replied"
                })
                replied_count += 1

    print(f"   Found {replied_count} new replies")

    # =========================================================================
    # PHASE 2: Get follow-ups due and pending new emails
    # =========================================================================
    print("\n[2/3] Gathering emails to send...")

    followup_1, followup_2 = sheets.get_followups_due(config.GOOGLE_SHEETS_ID)
    pending_new = sheets.get_pending_emails(config.GOOGLE_SHEETS_ID)

    print(f"   Follow-up #2 (final): {len(followup_2)}")
    print(f"   Follow-up #1 (bump):  {len(followup_1)}")
    print(f"   New outreach:         {len(pending_new)}")

    # Combine in priority order: followup_2 > followup_1 > new
    # Add email_type marker for each
    all_to_send = []
    for row in followup_2:
        row['_email_type'] = 'followup_2'
        all_to_send.append(row)
    for row in followup_1:
        row['_email_type'] = 'followup_1'
        all_to_send.append(row)
    for row in pending_new:
        row['_email_type'] = 'initial'
        all_to_send.append(row)

    if not all_to_send:
        click.secho("\n[OK] No emails to send today.", fg="green")
        return

    # Apply daily limit
    to_process = all_to_send[:config.DAILY_EMAIL_LIMIT]
    print(f"\n   Total to process: {len(to_process)} (limit: {config.DAILY_EMAIL_LIMIT})")

    estimated_time = len(to_process) * (config.MIN_DELAY_SECONDS + config.MAX_DELAY_SECONDS) / 2 / 60
    print(f"   Estimated time: ~{estimated_time:.1f} minutes")

    # =========================================================================
    # PHASE 3: Send emails
    # =========================================================================
    print("\n[3/3] Sending emails...")

    sent_count = 0
    failed_count = 0

    for i, job_data in enumerate(to_process, 1):
        email_type = job_data.get('_email_type', 'initial')
        recipient_email = job_data.get("Email", "")
        company = job_data.get("CompanyName", "Unknown")
        title = job_data.get("JobTitle", "Unknown")
        row_number = job_data.get("_row_number", 0)
        current_count = int(job_data.get("EmailCount", "0") or "0")

        type_label = {
            'initial': 'Initial',
            'followup_1': 'Follow-up #1',
            'followup_2': 'Follow-up #2'
        }.get(email_type, 'Unknown')

        print(f"\n[{i}/{len(to_process)}] {type_label}: {company} - {title}")
        print(f"   To: {recipient_email}")

        # Check for reply one more time before sending follow-up
        if email_type in ['followup_1', 'followup_2']:
            last_sent = job_data.get("LastEmailSentAt", "")[:10]
            if gmail.check_for_reply(recipient_email, last_sent):
                print("   [SKIP] Reply detected - skipping follow-up")
                sheets.update_row(config.GOOGLE_SHEETS_ID, row_number, {
                    "EmailStatus": "replied"
                })
                continue

        # Generate email based on type
        print("   Generating email...")
        original_subject = ""
        drafted = job_data.get("DraftedEmail", "")
        if drafted and "Subject:" in drafted:
            original_subject = drafted.split("Subject:")[1].split("\n")[0].strip()
            # Remove "Re: " prefix if present to get original
            original_subject = original_subject.replace("Re: ", "").strip()

        if email_type == 'initial':
            email_content = email_gen.generate_initial_email(job_data)
        elif email_type == 'followup_1':
            email_content = email_gen.generate_followup_1(job_data, original_subject or f"Interest in {title}")
        else:  # followup_2
            email_content = email_gen.generate_followup_2(job_data, original_subject or f"Interest in {title}")

        subject = email_content["subject"]
        body = email_content["body"]

        print(f"   Subject: {subject}")

        # Send email
        print("   Sending...")
        success = gmail.send_email(
            to=recipient_email,
            subject=subject,
            body=body
        )

        # Update sheet
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        next_followup = (datetime.now() + timedelta(days=config.FOLLOW_UP_DAYS)).strftime('%Y-%m-%d')
        new_count = current_count + 1

        if success:
            click.secho("   [OK] Sent successfully", fg="green")

            # Determine new status
            if new_count >= config.MAX_EMAILS_PER_CONTACT:
                new_status = "completed"
            elif email_type == 'initial':
                new_status = "sent"
            elif email_type == 'followup_1':
                new_status = "followed_up_1"
            else:
                new_status = "followed_up_2"

            sheets.update_row(config.GOOGLE_SHEETS_ID, row_number, {
                "EmailStatus": new_status,
                "EmailSentAt": timestamp,
                "EmailCount": str(new_count),
                "LastEmailSentAt": timestamp,
                "NextFollowUpDate": next_followup if new_count < config.MAX_EMAILS_PER_CONTACT else "",
                "DraftedEmail": f"Subject: {subject}\n\n{body}"
            })
            sent_count += 1
        else:
            click.secho("   [ERROR] Failed to send", fg="red")
            sheets.update_row(config.GOOGLE_SHEETS_ID, row_number, {
                "DraftedEmail": f"FAILED - Subject: {subject}\n\n{body}"
            })
            failed_count += 1

        # Random delay (skip on last email)
        if i < len(to_process):
            delay = random.randint(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS)
            print(f"   Waiting {delay}s before next email...")
            time.sleep(delay)

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    click.secho("SUMMARY", fg="blue", bold=True)
    print("=" * 70)
    print(f"   Replies detected:     {replied_count}")
    print(f"   Emails sent:          {sent_count}")
    print(f"   Failed:               {failed_count}")
    print(f"   Remaining in queue:   {len(all_to_send) - len(to_process)}")
    print("=" * 70)


if __name__ == "__main__":
    run_outreach_flow()
