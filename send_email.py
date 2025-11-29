#!/usr/bin/env python3
"""
Gmail Agent - Send and summarize emails via Gmail API + OpenAI
"""

import argparse
import base64
import json
import os
import sys
from typing import Dict, Optional

from email.mime.text import MIMEText

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from openai import OpenAI


# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


def get_credentials():
    """Get valid user credentials from storage or prompt for authorization."""
    creds = None
    token_file = 'token.json'
    credentials_file = 'credentials.json'
    
    # Load existing token
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_file):
                print(f"Error: {credentials_file} not found!")
                print("Please download it from Google Cloud Console.")
                sys.exit(1)
            
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    
    return creds


def load_openai_api_key(credentials_file: str = 'credentials.json') -> str:
    """Load the OpenAI API key from env or credentials.json."""
    env_key = os.getenv('OPENAI_API_KEY')
    if env_key:
        return env_key

    if os.path.exists(credentials_file):
        try:
            with open(credentials_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Unable to parse {credentials_file}: {exc}") from exc

        # Allow either top-level key or nested structure
        openai_key = data.get('openai_api_key')
        if not openai_key and 'openai' in data:
            openai_key = data['openai'].get('api_key')

        if openai_key:
            return openai_key

    raise ValueError(
        "OpenAI API key not found. Set OPENAI_API_KEY env var or add "
        "'openai_api_key' to credentials.json."
    )


def create_message(to, subject, body):
    """Create a message for an email."""
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw_message}


def send_message(service, user_id, message):
    """Send an email message."""
    try:
        message = service.users().messages().send(
            userId=user_id, body=message).execute()
        print(f'Message Id: {message["id"]}')
        return message
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None


def decode_base64url(data: str) -> str:
    """Decode a base64url string safely."""
    if not data:
        return ""
    padding = '=' * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding).decode('utf-8', errors='ignore')


def extract_plain_text(payload: Dict) -> str:
    """Recursively extract the plain text body from a Gmail payload."""
    if not payload:
        return ""

    mime_type = payload.get('mimeType', '')
    body = payload.get('body', {})
    data = body.get('data')

    if mime_type == 'text/plain' and data:
        return decode_base64url(data)

    # multipart payload
    for part in payload.get('parts', []):
        text = extract_plain_text(part)
        if text:
            return text

    # Fallback to snippet of other mime types
    if data:
        return decode_base64url(data)

    return ""


def fetch_latest_email(service):
    """Retrieve the most recent email from the user's inbox."""
    messages_response = service.users().messages().list(
        userId='me',
        maxResults=1,
        q='in:inbox'
    ).execute()

    messages = messages_response.get('messages', [])
    if not messages:
        print("📭 Inbox is empty.")
        return None

    message_id = messages[0]['id']
    message = service.users().messages().get(
        userId='me',
        id=message_id,
        format='full'
    ).execute()

    headers = message.get('payload', {}).get('headers', [])
    header_map = {h['name'].lower(): h['value'] for h in headers}
    subject = header_map.get('subject', '(No Subject)')
    sender = header_map.get('from', '(Unknown Sender)')
    snippet = message.get('snippet', '').strip()
    body_text = extract_plain_text(message.get('payload', {}))

    return {
        'id': message_id,
        'subject': subject,
        'from': sender,
        'snippet': snippet,
        'body': body_text or snippet
    }


def summarize_email_content(content: Dict, client: OpenAI) -> str:
    """Summarize email content using OpenAI."""
    body_preview = content.get('body', '')[:4000]  # keep prompt lightweight
    prompt = (
        "Summarize the following email in three concise bullet points. "
        "Highlight the sender intent and any action items.\n\n"
        f"From: {content.get('from')}\n"
        f"Subject: {content.get('subject')}\n"
        "Body:\n"
        f"{body_preview}"
    )

    response = client.responses.create(
        model="gpt-4o-mini",
        input=prompt,
        temperature=0.2
    )

    summary_text = response.output[0].content[0].text
    return summary_text.strip()


def summarize_latest_email(service):
    """Fetch the latest email and summarize it."""
    latest = fetch_latest_email(service)
    if not latest:
        return

    try:
        api_key = load_openai_api_key()
        client = OpenAI(api_key=api_key)
    except ValueError as exc:
        print(f"❌ {exc}")
        sys.exit(1)

    print("📥 Latest email:")
    print(f"From: {latest['from']}")
    print(f"Subject: {latest['subject']}")
    if latest['snippet']:
        print(f"Snippet: {latest['snippet']}")

    print("\n🧠 Generating summary...")
    try:
        summary = summarize_email_content(latest, client)
    except Exception as exc:
        print(f"❌ Failed to summarize email: {exc}")
        sys.exit(1)

    print("\n📌 Summary:")
    print(summary)


def send_email_flow(service, recipient_email: Optional[str] = None):
    """Handle sending the template email."""
    if not recipient_email:
        recipient_email = os.getenv('RECIPIENT_EMAIL')

    if not recipient_email:
        recipient_email = input("Enter recipient email address: ").strip()

    subject = "Hello from Gullie Agent"
    body = "hello from jolie"

    print(f"Sending email to: {recipient_email}")
    print(f"Subject: {subject}")
    print(f"Body: {body}")

    message = create_message(recipient_email, subject, body)
    result = send_message(service, 'me', message)

    if result:
        print("✅ Email sent successfully!")
    else:
        print("❌ Failed to send email")
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(description="Gullie Gmail Agent")
    parser.add_argument(
        '--action',
        choices=['send', 'summarize'],
        default='send',
        help="Choose whether to send the templated email or summarize the latest email."
    )
    parser.add_argument(
        'recipient',
        nargs='?',
        help="Recipient email address (only used for send action)."
    )
    return parser.parse_args()


def main():
    """Entry point for the CLI tool."""
    args = parse_args()

    try:
        creds = get_credentials()
        service = build('gmail', 'v1', credentials=creds)
    except Exception as exc:
        print(f"❌ Failed to authenticate with Gmail: {exc}")
        sys.exit(1)

    if args.action == 'send':
        send_email_flow(service, args.recipient)
    else:
        summarize_latest_email(service)


if __name__ == '__main__':
    main()

