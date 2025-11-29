#!/usr/bin/env python3
"""
Gmail Agent - Send emails via Gmail API
"""

import os
import sys
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


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


def create_message(to, subject, body):
    """Create a message for an email."""
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}


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


def main():
    """Main function to send email."""
    # Get recipient email from environment variable or command line
    recipient_email = os.getenv('RECIPIENT_EMAIL')
    
    if not recipient_email:
        if len(sys.argv) > 1:
            recipient_email = sys.argv[1]
        else:
            recipient_email = input("Enter recipient email address: ")
    
    # Email content
    subject = "Hello from Gullie Agent"
    body = "hello from jolie"
    
    print(f"Sending email to: {recipient_email}")
    print(f"Subject: {subject}")
    print(f"Body: {body}")
    
    try:
        # Get credentials and build service
        creds = get_credentials()
        service = build('gmail', 'v1', credentials=creds)
        
        # Create and send message
        message = create_message(recipient_email, subject, body)
        result = send_message(service, 'me', message)
        
        if result:
            print("✅ Email sent successfully!")
        else:
            print("❌ Failed to send email")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

