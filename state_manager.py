#!/usr/bin/env python3
"""
State Manager - Persist and manage workflow state for each employee case
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional, Any


class StateManager:
    """Manages persistent state for email orchestration workflow."""
    
    def __init__(self, state_file: str = 'state.json'):
        self.state_file = state_file
        self._state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load state from JSON file, creating empty structure if it doesn't exist."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️  Error loading state file: {e}. Creating new state.")
        
        return {"cases": {}}
    
    def _save_state(self):
        """Save state to JSON file."""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"❌ Error saving state file: {e}")
            raise
    
    def get_case(self, employee_email: str) -> Optional[Dict[str, Any]]:
        """Retrieve case state for an employee."""
        return self._state.get("cases", {}).get(employee_email)
    
    def create_case(self, employee_email: str) -> Dict[str, Any]:
        """Initialize a new case for an employee."""
        if employee_email in self._state.get("cases", {}):
            return self._state["cases"][employee_email]
        
        case = {
            "employee_email": employee_email,
            "current_milestone": 1,
            "milestone_1": {
                "status": "in_progress",
                "data": {
                    "pickup_address": None,
                    "delivery_address": None,
                    "needs_box": None,
                    "needs_packing_help": None,
                    "insurance_opted_in": None
                },
                "pending_actions": ["waiting_for_addresses"]
            },
            "created_at": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat()
        }
        
        if "cases" not in self._state:
            self._state["cases"] = {}
        
        self._state["cases"][employee_email] = case
        self._save_state()
        return case
    
    def update_milestone_data(self, employee_email: str, milestone: int, data: Dict[str, Any]):
        """Update collected data for a specific milestone."""
        case = self.get_case(employee_email)
        if not case:
            raise ValueError(f"Case not found for employee: {employee_email}")
        
        milestone_key = f"milestone_{milestone}"
        if milestone_key not in case:
            case[milestone_key] = {
                "status": "in_progress",
                "data": {},
                "pending_actions": []
            }
        
        # Update data fields
        if "data" not in case[milestone_key]:
            case[milestone_key]["data"] = {}
        
        case[milestone_key]["data"].update(data)
        case["last_updated"] = datetime.utcnow().isoformat()
        
        self._save_state()
    
    def advance_milestone(self, employee_email: str):
        """Move to the next milestone."""
        case = self.get_case(employee_email)
        if not case:
            raise ValueError(f"Case not found for employee: {employee_email}")
        
        current = case["current_milestone"]
        
        # Mark current milestone as completed
        milestone_key = f"milestone_{current}"
        if milestone_key in case:
            case[milestone_key]["status"] = "completed"
        
        # Advance to next milestone
        case["current_milestone"] = current + 1
        case["last_updated"] = datetime.utcnow().isoformat()
        
        self._save_state()
    
    def is_milestone_complete(self, employee_email: str, milestone: int) -> bool:
        """Check if a milestone is complete based on completion criteria."""
        case = self.get_case(employee_email)
        if not case:
            return False
        
        if milestone == 1:
            milestone_data = case.get("milestone_1", {}).get("data", {})
            return all([
                milestone_data.get("pickup_address") is not None,
                milestone_data.get("delivery_address") is not None,
                milestone_data.get("needs_box") is not None,
                milestone_data.get("needs_packing_help") is not None,
                milestone_data.get("insurance_opted_in") is not None
            ])
        
        # For other milestones, implement as needed
        return False
    
    def update_pending_actions(self, employee_email: str, milestone: int, actions: list):
        """Update pending actions for a milestone."""
        case = self.get_case(employee_email)
        if not case:
            raise ValueError(f"Case not found for employee: {employee_email}")
        
        milestone_key = f"milestone_{milestone}"
        if milestone_key not in case:
            case[milestone_key] = {"status": "in_progress", "data": {}, "pending_actions": []}
        
        case[milestone_key]["pending_actions"] = actions
        case["last_updated"] = datetime.utcnow().isoformat()
        self._save_state()
    
    def get_all_cases(self) -> Dict[str, Dict[str, Any]]:
        """Get all cases."""
        return self._state.get("cases", {})

