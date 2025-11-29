#!/usr/bin/env python3
"""
View current state - Helper script to inspect state.json
"""

import json
import sys
from state_manager import StateManager


def view_state():
    """Display current state in a readable format."""
    sm = StateManager()
    all_cases = sm.get_all_cases()
    
    if not all_cases:
        print("📭 No cases found in state.json")
        return
    
    print("=" * 60)
    print("Current State Overview")
    print("=" * 60 + "\n")
    
    for employee_email, case in all_cases.items():
        print(f"👤 Employee: {employee_email}")
        print(f"   Current Milestone: {case.get('current_milestone', 'N/A')}")
        print(f"   Created: {case.get('created_at', 'N/A')}")
        print(f"   Last Updated: {case.get('last_updated', 'N/A')}")
        
        # Show Milestone 1 data
        milestone_1 = case.get('milestone_1', {})
        if milestone_1:
            status = milestone_1.get('status', 'unknown')
            print(f"   Milestone 1 Status: {status}")
            
            data = milestone_1.get('data', {})
            print("   Data Collected:")
            for field, value in data.items():
                if value is not None:
                    print(f"      ✅ {field}: {value}")
                else:
                    print(f"      ⏳ {field}: (not collected)")
            
            pending = milestone_1.get('pending_actions', [])
            if pending:
                print(f"   Pending Actions: {', '.join(pending)}")
        
        print()
    
    print("=" * 60)
    print("Raw JSON (for debugging):")
    print("=" * 60)
    print(json.dumps(all_cases, indent=2))


if __name__ == '__main__':
    try:
        view_state()
    except FileNotFoundError:
        print("❌ state.json not found. Run the orchestrator first to create state.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error viewing state: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

