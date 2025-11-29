#!/usr/bin/env python3
"""
Decision Engine - Determine next action based on current state and incoming email
"""

from typing import Dict, List, Optional, Any

from state_manager import StateManager


class DecisionEngine:
    """Determines next actions based on state and email content."""
    
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
    
    def get_next_action(self, state: Dict[str, Any], parsed_email: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Main decision logic - determine next action based on state and email."""
        current_milestone = state.get("current_milestone", 1)
        
        if current_milestone == 1:
            return self._get_milestone1_action(state, parsed_email)
        
        # For future milestones
        return None
    
    def _get_milestone1_action(self, state: Dict[str, Any], parsed_email: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Determine action for Milestone 1."""
        milestone_1 = state.get("milestone_1", {})
        data = milestone_1.get("data", {})
        
        # Check if this is an initial request (no data collected yet)
        if all(v is None for v in data.values()):
            return {
                "type": "send_initial_request",
                "to": state["employee_email"],
                "milestone": 1
            }
        
        # Check if milestone is complete
        if self.check_milestone1_completion(state):
            return {
                "type": "send_completion_confirmation",
                "to": state["employee_email"],
                "milestone": 1
            }
        
        # Check for missing fields
        missing_fields = self.determine_missing_fields(state)
        if missing_fields:
            return {
                "type": "send_followup",
                "to": state["employee_email"],
                "milestone": 1,
                "missing_fields": missing_fields
            }
        
        return None
    
    def check_milestone1_completion(self, state: Dict[str, Any]) -> bool:
        """Rule-based completion check for Milestone 1."""
        milestone_1 = state.get("milestone_1", {})
        data = milestone_1.get("data", {})
        
        required_fields = [
            "pickup_address",
            "delivery_address",
            "needs_box",
            "needs_packing_help",
            "insurance_opted_in"
        ]
        
        return all(data.get(field) is not None for field in required_fields)
    
    def determine_missing_fields(self, state: Dict[str, Any]) -> List[str]:
        """Identify what data is still needed for Milestone 1."""
        milestone_1 = state.get("milestone_1", {})
        data = milestone_1.get("data", {})
        
        required_fields = [
            "pickup_address",
            "delivery_address",
            "needs_box",
            "needs_packing_help",
            "insurance_opted_in"
        ]
        
        missing = []
        for field in required_fields:
            if data.get(field) is None:
                missing.append(field)
        
        return missing
    
    def should_process_email(self, parsed_email: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """Determine if an email should be processed for this case."""
        # Check if email is from the employee
        sender_email = parsed_email.get("from", "")
        employee_email = state.get("employee_email", "")
        
        # Simple check: extract email from "Name <email>" format
        if employee_email.lower() in sender_email.lower():
            return True
        
        return False
    
    def extract_action_from_email(self, parsed_email: Dict[str, Any], intent: str) -> Optional[Dict[str, Any]]:
        """Extract action information from email based on intent."""
        if intent == "answer":
            return {
                "type": "extract_data",
                "email": parsed_email
            }
        elif intent == "question":
            return {
                "type": "handle_question",
                "email": parsed_email
            }
        elif intent == "greeting":
            return {
                "type": "send_initial_request",
                "email": parsed_email
            }
        
        return None

