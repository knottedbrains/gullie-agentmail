#!/usr/bin/env python3
"""
Main Runner - CLI tool to run the orchestrator (poll emails or process single email)
"""

import argparse
import time
from googleapiclient.discovery import build

from orchestrator import Orchestrator
from send_email import get_credentials, fetch_latest_email, extract_plain_text


def poll_inbox(orchestrator: Orchestrator, interval: int = 60):
    """Check for new emails periodically."""
    print(f"🔄 Starting email polling (checking every {interval} seconds)...")
    print("Press Ctrl+C to stop\n")
    
    processed_ids = set()
    
    try:
        while True:
            try:
                # Fetch latest email
                latest = fetch_latest_email(orchestrator.service)
                
                if latest:
                    email_id = latest.get('id')
                    
                    # Skip if already processed
                    if email_id in processed_ids:
                        print(f"⏭️  Email {email_id} already processed, skipping...")
                    else:
                        print(f"\n📧 Processing new email: {latest.get('subject', 'No Subject')}")
                        print(f"   From: {latest.get('from', 'Unknown')}")
                        
                        success = orchestrator.process_incoming_email(latest)
                        if success:
                            processed_ids.add(email_id)
                            print("✅ Email processed successfully")
                        else:
                            print("⚠️  Email processing had issues")
                else:
                    print("📭 No new emails")
                
                # Wait before next check
                time.sleep(interval)
                
            except KeyboardInterrupt:
                print("\n\n🛑 Stopping email polling...")
                break
            except Exception as e:
                print(f"❌ Error during polling: {e}")
                time.sleep(interval)
                
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")


def process_latest_email(orchestrator: Orchestrator):
    """Process the most recent email (for testing)."""
    print("📥 Fetching latest email...")
    
    latest = fetch_latest_email(orchestrator.service)
    if not latest:
        print("📭 No emails found in inbox")
        return
    
    print(f"\n📧 Processing email:")
    print(f"   From: {latest.get('from', 'Unknown')}")
    print(f"   Subject: {latest.get('subject', 'No Subject')}")
    print(f"   Snippet: {latest.get('snippet', '')[:100]}...")
    
    success = orchestrator.process_incoming_email(latest)
    if success:
        print("\n✅ Email processed successfully")
    else:
        print("\n⚠️  Email processing had issues")


def initiate_case(orchestrator: Orchestrator, employee_email: str):
    """Manually initiate a new case by sending initial request."""
    print(f"🚀 Initiating new case for {employee_email}...")
    
    success = orchestrator.initiate_case(employee_email)
    if success:
        print(f"✅ Initial request sent to {employee_email}")
    else:
        print(f"❌ Failed to send initial request to {employee_email}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Gullie Email Orchestrator - Process emails and manage workflow"
    )
    parser.add_argument(
        '--mode',
        choices=['poll', 'latest', 'initiate'],
        default='latest',
        help="Operation mode: poll (continuous), latest (process one), or initiate (start new case)"
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help="Polling interval in seconds (only for poll mode, default: 60)"
    )
    parser.add_argument(
        '--email',
        type=str,
        help="Employee email address (required for initiate mode)"
    )
    return parser.parse_args()


def main():
    """Entry point for the CLI tool."""
    args = parse_args()
    
    # Validate arguments
    if args.mode == 'initiate' and not args.email:
        print("❌ Error: --email is required for initiate mode")
        return
    
    # Authenticate with Gmail
    try:
        print("🔐 Authenticating with Gmail...")
        creds = get_credentials()
        service = build('gmail', 'v1', credentials=creds)
        print("✅ Authenticated successfully\n")
    except Exception as exc:
        print(f"❌ Failed to authenticate with Gmail: {exc}")
        return
    
    # Create orchestrator
    orchestrator = Orchestrator(service)
    
    # Execute based on mode
    if args.mode == 'poll':
        poll_inbox(orchestrator, args.interval)
    elif args.mode == 'latest':
        process_latest_email(orchestrator)
    elif args.mode == 'initiate':
        initiate_case(orchestrator, args.email)


if __name__ == '__main__':
    main()

