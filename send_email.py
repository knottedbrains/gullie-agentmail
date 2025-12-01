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
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.readonly'
]


def get_credentials():
    """Get valid user credentials from storage or prompt for authorization."""
    creds = None
    token_file = 'token.json'
    credentials_file = 'credentials.json'
    
    # Load existing token
    if os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
            # Check if the token has all required scopes
            if creds and creds.valid:
                token_scopes = set(creds.scopes or [])
                required_scopes = set(SCOPES)
                if not required_scopes.issubset(token_scopes):
                    print("⚠️  Token missing required scopes. Re-authorizing...")
                    creds = None  # Force re-authorization
        except Exception as e:
            print(f"⚠️  Error loading token: {e}. Re-authorizing...")
            creds = None
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                # If refresh fails, re-authorize
                creds = None
        
        if not creds or not creds.valid:
            if not os.path.exists(credentials_file):
                print(f"Error: {credentials_file} not found!")
                print("Please download it from Google Cloud Console.")
                sys.exit(1)
            
            print("🔐 Authorizing application...")
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


def create_message(to, subject, body, thread_id=None, in_reply_to_message_id=None, service=None):
    """Create a message for an email. Optionally reply to an existing thread.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body
        thread_id: Gmail thread ID to reply in
        in_reply_to_message_id: Message-ID header of the email being replied to
        service: Gmail service (optional, used to fetch latest message if thread_id provided)
    
    Note: For proper threading, we need the Message-ID of the latest message in the thread.
    If thread_id is provided but in_reply_to_message_id is not, we'll try to fetch it.
    """
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    
    # If we have a thread_id but no message_id, try to get the latest message in the thread
    if thread_id and not in_reply_to_message_id and service:
        latest_msg = get_latest_message_in_thread(service, thread_id)
        if latest_msg and latest_msg.get('message_id_header'):
            in_reply_to_message_id = latest_msg['message_id_header']
            print(f"📧 Using Message-ID from latest message in thread: {in_reply_to_message_id[:50]}...")
    
    # If replying to a message, add proper reply headers (this is what actually makes it thread)
    if in_reply_to_message_id:
        # Message-ID should already be in angle brackets, but ensure it is
        if not in_reply_to_message_id.startswith('<'):
            in_reply_to_message_id = f'<{in_reply_to_message_id}>'
        
        message['In-Reply-To'] = in_reply_to_message_id
        message['References'] = in_reply_to_message_id
        print(f"📎 Added In-Reply-To header: {in_reply_to_message_id[:50]}...")
    
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    result = {'raw': raw_message}
    
    # Include threadId if provided (helps Gmail associate it, but headers are what actually thread it)
    if thread_id:
        result['threadId'] = thread_id
    
    return result


# TODO: human in the loop
def send_message(service, user_id, message, real_run = False):
    """Send an email message."""
    try:
        if real_run:
            message = service.users().messages().send(
                userId=user_id, body=message).execute()
            print(f'Message Id: {message["id"]}')
            print(f"Thread Id: {message['threadId']}")
            return message
        else:
            print(message)
            return "Email sent(Dry Run)"
        
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


def fetch_email_by_id(service, message_id: str):
    """Retrieve a specific email by message ID."""
    try:
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
        
        # Include threadId and internalDate for thread handling
        thread_id = message.get('threadId')
        internal_date = message.get('internalDate')
        message_id_header = header_map.get('message-id', '')

        return {
            'id': message_id,
            'subject': subject,
            'from': sender,
            'snippet': snippet,
            'body': body_text or snippet,
            'threadId': thread_id,
            'internalDate': internal_date,
            'message_id_header': message_id_header
        }
    except HttpError as error:
        print(f'❌ Error fetching email {message_id}: {error}')
        return None


def get_latest_message_in_thread(service, thread_id: str):
    """Get the latest message in a thread to extract its Message-ID for replying."""
    try:
        thread_messages = fetch_thread_messages(service, thread_id)
        if not thread_messages:
            return None
        
        # Find the message with the highest internalDate (most recent)
        latest_message = max(
            thread_messages,
            key=lambda msg: int(msg.get('internalDate', 0))
        )
        
        # Fetch full message details to get headers
        message_id = latest_message['id']
        return fetch_email_by_id(service, message_id)
    except Exception as e:
        print(f'⚠️  Error getting latest message in thread: {e}')
        return None


def fetch_thread_messages(service, thread_id: str):
    """Fetch all messages in a thread."""
    try:
        thread = service.users().threads().get(
            userId='me',
            id=thread_id,
            format='full'
        ).execute()
        
        messages = thread.get('messages', [])
        return messages
    except HttpError as error:
        print(f'❌ Error fetching thread {thread_id}: {error}')
        return []


def is_latest_in_thread(service, email: Dict) -> bool:
    """Check if the given email is the latest message in its thread."""
    thread_id = email.get('threadId')
    if not thread_id:
        # No thread ID means it's a standalone email, so it's the "latest"
        return True
    
    current_internal_date = email.get('internalDate')
    if not current_internal_date:
        # Can't determine, assume it's latest to be safe
        return True
    
    # Fetch all messages in the thread
    thread_messages = fetch_thread_messages(service, thread_id)
    if not thread_messages:
        return True
    
    # Find the message with the highest internalDate
    latest_date = max(
        (msg.get('internalDate', 0) for msg in thread_messages),
        default=0
    )
    
    # Check if current email is the latest
    return int(current_internal_date) >= int(latest_date)


def fetch_recent_emails(service, max_results: int = 5):
    """Retrieve recent emails from the user's inbox."""
    messages_response = service.users().messages().list(
        userId='me',
        maxResults=max_results,
        q='in:inbox'
    ).execute()

    messages = messages_response.get('messages', [])
    if not messages:
        return []

    emails = []
    for msg in messages:
        email = fetch_email_by_id(service, msg['id'])
        if email:
            emails.append(email)
    
    return emails


def fetch_latest_email(service):
    """Retrieve the most recent email from the user's inbox."""
    emails = fetch_recent_emails(service, max_results=1)
    return emails[0] if emails else None


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
        input=prompt
    )

    # Extract summary from response
    # Response structure: response.output[0].content[0].text
    try:
        summary_text = response.output[0].content[0].text
        return summary_text.strip()
    except (AttributeError, IndexError, KeyError) as e:
        raise ValueError(f"Unable to extract text from OpenAI response: {e}")


def summarize_latest_email(service):
    """Fetch the latest email and summarize it."""
    latest = fetch_latest_email(service)
    if not latest:
        return

    try:
        api_key = load_openai_api_key()
        # Set API key via environment variable if not already set
        if not os.getenv('OPENAI_API_KEY'):
            os.environ['OPENAI_API_KEY'] = api_key
        client = OpenAI()
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

