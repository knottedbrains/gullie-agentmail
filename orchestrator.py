#!/usr/bin/env python3
"""
Orchestrator - Main coordination logic that ties everything together
"""

import json
from typing import Dict, Optional, Any

from decision_engine import DecisionEngine
from email_parser import EmailParser
from email_templates import (
    get_milestone1_initial_request,
    get_milestone1_followup,
    get_milestone1_completion_confirmation,
    get_clarification_request
)
from state_manager import StateManager
from send_email import create_message, send_message, is_latest_in_thread


class Orchestrator:
    """Main orchestration agent that processes emails and manages workflow."""
    
    def __init__(self, gmail_service, state_manager: Optional[StateManager] = None):
        self.service = gmail_service
        self.state_manager = state_manager or StateManager()
        self.email_parser = EmailParser(gmail_service=gmail_service)
        self.decision_engine = DecisionEngine(self.state_manager)
    
    def process_incoming_email(self, email: Dict[str, Any]) -> bool:
        """Main entry point for email processing."""
        try:
            # Check if this is the latest email in the thread
            if not is_latest_in_thread(self.service, email):
                print(f"⏭️  Skipping email {email.get('id')}: not the latest in thread")
                return False
            
            # Parse email
            parsed_email = self.email_parser.parse_email(email)
            
            # Extract sender email
            sender_email = self.email_parser.extract_email_address(parsed_email["from"])
            if not sender_email:
                print("⚠️  Could not extract sender email address")
                return False
            
            # Get or create case for this employee
            case = self.state_manager.get_case(sender_email)
            if not case:
                # New case - create it
                case = self.state_manager.create_case(sender_email)
                print(f"📝 Created new case for {sender_email}")
            
            # Update employee thread ID if this email is part of a thread
            thread_id = email.get('threadId')
            if thread_id:
                current_thread_id = case.get("employee_thread_id")
                if not current_thread_id:
                    # First time seeing this thread
                    self.state_manager.update_thread_id(sender_email, "employee", thread_id)
                    print(f"📧 Linked employee thread: {thread_id}")
                elif current_thread_id != thread_id:
                    # Thread ID changed (shouldn't happen often, but update it)
                    self.state_manager.update_thread_id(sender_email, "employee", thread_id)
                    print(f"📧 Updated employee thread: {thread_id}")
            
            # Identify email intent
            intent = self.email_parser.extract_intent(parsed_email["body"])
            print(f"📧 Email intent: {intent}")
            
            # Handle based on current milestone
            current_milestone = case["current_milestone"]
            if current_milestone == 1:
                return self.handle_milestone1(parsed_email, case, intent)
            
            # Future milestones can be added here
            print(f"⚠️  Milestone {current_milestone} not yet implemented")
            return False
            
        except Exception as e:
            print(f"❌ Error processing email: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def handle_milestone1(self, parsed_email: Dict, case: Dict, intent: str) -> bool:
        """Handle Milestone 1 specific logic."""
        employee_email = case["employee_email"]
        milestone_1 = case.get("milestone_1", {})
        data = milestone_1.get("data", {})
        
        # If intent is answer, try to extract data
        if intent == "answer":
            print("🔍 Extracting data from email...")

            context = self.email_parser.get_context_of_thread(case["employee_thread_id"])
            extracted_data = self.email_parser.extract_milestone1_data(parsed_email["body"], context)
            
            # Update state with extracted data (only non-None values)
            updates = {k: v for k, v in extracted_data.items() if v is not None}
            if updates:
                self.state_manager.update_milestone_data(employee_email, 1, updates)
                print(f"✅ Updated data: {list(updates.keys())}")
            
            # Refresh case state
            case = self.state_manager.get_case(employee_email)
        
        # Determine next action
        next_action = self.decision_engine.get_next_action(case, parsed_email)
        if next_action:
            print("next action:", json.dumps(next_action, indent=2))
        else:
            print("next action: None")
        
        if next_action:
            return self.execute_action(next_action, case)
        
        return True
    
    def execute_action(self, action: Dict[str, Any], case: Dict[str, Any]) -> bool:
        """Execute the determined action."""
        action_type = action.get("type")
        employee_email = case["employee_email"]
        
        try:
            if action_type == "send_initial_request":
                subject, body = get_milestone1_initial_request()
                return self.send_next_email(employee_email, subject, body)
            
            elif action_type == "send_followup":
                missing_fields = action.get("missing_fields", [])
                subject, body = get_milestone1_followup(missing_fields)
                return self.send_next_email(employee_email, subject, body)
            
            elif action_type == "send_completion_confirmation":
                subject, body = get_milestone1_completion_confirmation()
                success = self.send_next_email(employee_email, subject, body)
                if success:
                    # Mark milestone as complete and advance
                    if self.state_manager.is_milestone_complete(employee_email, 1):
                        self.state_manager.advance_milestone(employee_email)
                        print(f"🎉 Milestone 1 completed for {employee_email}")
                return success
            
            elif action_type == "send_clarification":
                unclear_field = action.get("field", "")
                subject, body = get_clarification_request(unclear_field)
                return self.send_next_email(employee_email, subject, body)
            
            else:
                print(f"⚠️  Unknown action type: {action_type}")
                return False
                
        except Exception as e:
            print(f"❌ Error executing action {action_type}: {e}")
            return False
    
    def send_next_email(self, employee_email: str, subject: str, body: str, thread_type: str = "employee") -> bool:
        """Execute email sending. Optionally reply in an existing thread.
        
        Args:
            employee_email: Email address of the recipient
            subject: Email subject
            body: Email body
            thread_type: "employee" or "vendor" - determines which thread to use
        """
        try:
            # Get the case to check for existing thread
            case = self.state_manager.get_case(employee_email)
            thread_id = None
            
            if case:
                if thread_type == "employee":
                    thread_id = case.get("employee_thread_id")
                elif thread_type == "vendor":
                    thread_id = case.get("vendor_thread_id")
            
            # Create message with optional thread_id
            # Pass service so we can fetch the latest message's Message-ID for proper threading
            message = create_message(
                employee_email, 
                subject, 
                body, 
                thread_id=thread_id,
                service=self.service if thread_id else None
            )
            result = send_message(self.service, 'me', message, True)
            
            if result:
                # If this was a new thread (no thread_id before), save the thread_id from the sent message
                if result and isinstance(result, dict) and "threadId" in result:
                    new_thread_id = result["threadId"]
                    if not thread_id:  # This was a new thread
                        self.state_manager.update_thread_id(employee_email, thread_type, new_thread_id)
                        print(f"📧 Started new {thread_type} thread: {new_thread_id}")
                    elif thread_id != new_thread_id:
                        # Thread ID changed (shouldn't happen, but update just in case)
                        self.state_manager.update_thread_id(employee_email, thread_type, new_thread_id)
                
                print(f"✅ Email sent to {employee_email}")
                return True
            else:
                print(f"❌ Failed to send email to {employee_email}")
                return False
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            return False
    
    def initiate_case(self, employee_email: str) -> bool:
        """Manually initiate a new case by sending initial request."""
        case = self.state_manager.get_case(employee_email)
        if not case:
            case = self.state_manager.create_case(employee_email)
        
        subject, body = get_milestone1_initial_request()
        return self.send_next_email(employee_email, subject, body)
