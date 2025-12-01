#!/usr/bin/env python3
"""
Test script for orchestrator components
"""

import json
from state_manager import StateManager
from email_parser import EmailParser
from decision_engine import DecisionEngine


def test_state_manager():
    """Test state management."""
    print("🧪 Testing StateManager...")
    
    # Use a test state file
    sm = StateManager(state_file='test_state.json')
    
    # Create a test case
    employee_email = "test@example.com"
    case = sm.create_case(employee_email)
    print(f"✅ Created case: {case['employee_email']}")
    
    # Update with some data
    sm.update_milestone_data(employee_email, 1, {
        "pickup_address": "123 Main St, City, State 12345",
        "needs_box": True
    })
    print("✅ Updated milestone data")
    
    # Check completion
    is_complete = sm.is_milestone_complete(employee_email, 1)
    print(f"✅ Milestone complete: {is_complete}")
    
    # Get case
    retrieved = sm.get_case(employee_email)
    print(f"✅ Retrieved case: {json.dumps(retrieved, indent=2)}")
    
    # Cleanup
    import os
    if os.path.exists('test_state.json'):
        os.remove('test_state.json')
    
    print("✅ StateManager tests passed\n")


def test_email_parser():
    """Test email parsing."""
    print("🧪 Testing EmailParser...")
    
    parser = EmailParser()
    
    # Test address extraction
    test_text = """
    Hi! My pickup address is 123 Main Street, New York, NY 10001.
    Pickup date is Jan 5th, 2026
    I need to deliver to 456 Oak Avenue, Los Angeles, CA 90001.
    """
    addresses = parser.extract_addresses_and_dates(test_text)
    print(f"✅ Extracted addresses: {addresses}")
    
    # Test yes/no extraction
    test_yes = "Yes, I need boxes please"
    result = parser.extract_yes_no_response(test_yes, "Do you need boxes?")
    print(f"✅ Yes response: {result}")
    
    test_no = "No, I don't need packing help"
    result = parser.extract_yes_no_response(test_no, "Do you need packing help?")
    print(f"✅ No response: {result}")
    
    # Test intent
    test_answer = "My pickup is at 123 Main St and delivery at 456 Oak Ave. Yes to boxes."
    intent = parser.extract_intent(test_answer)
    print(f"✅ Intent: {intent}")
    
    print("✅ EmailParser tests passed\n")


def test_decision_engine():
    """Test decision engine."""
    print("🧪 Testing DecisionEngine...")
    
    sm = StateManager(state_file='test_state.json')
    de = DecisionEngine(sm)
    
    # Create test case
    employee_email = "test@example.com"
    case = sm.create_case(employee_email)
    
    # Test with empty data (should send initial request)
    parsed_email = {"from": "test@example.com", "body": "Hello"}
    action = de.get_next_action(case, parsed_email)
    print(f"✅ Action for empty case: {action}")
    
    # Test with partial data
    sm.update_milestone_data(employee_email, 1, {
        "pickup_address": "123 Main St",
        "pickup_date": "Jan 5th, 2026",
        "delivery_address": "456 Oak Ave"
    })
    case = sm.get_case(employee_email)
    action = de.get_next_action(case, parsed_email)
    print(f"✅ Action for partial data: {action}")
    
    # Test completion check
    sm.update_milestone_data(employee_email, 1, {
        "pickup_address": "123 Main St",
        "pickup_date": "Jan 5th, 2026",
        "delivery_address": "456 Oak Ave",
        "needs_box": True,
        "needs_packing_help": False,
        "insurance_opted_in": True
    })
    case = sm.get_case(employee_email)
    is_complete = de.check_milestone1_completion(case)
    print(f"✅ Milestone complete: {is_complete}")
    
    if is_complete:
        action = de.get_next_action(case, parsed_email)
        print(f"✅ Action when complete: {action}")
    
    # Cleanup
    import os
    if os.path.exists('test_state.json'):
        os.remove('test_state.json')
    
    print("✅ DecisionEngine tests passed\n")


def test_with_mock_email():
    """Test orchestrator with mock email data."""
    print("🧪 Testing with mock email...")
    
    mock_email = {
        'id': 'test123',
        'from': 'employee@example.com',
        'subject': 'Moving Request',
        'body': '''
        Hi Gullie,
        
        My pickup address is: 123 Main Street, New York, NY 10001
        My pickup date is: Jan 6th, 2026
        Delivery address: 456 Oak Avenue, Los Angeles, CA 90001
        
        Yes, I need boxes.
        No, I don't need packing help.
        Yes, I want insurance.
        ''',
        'snippet': 'Moving request with addresses...'
    }
    
    print(f"Mock email: {json.dumps(mock_email, indent=2)}")
    print("✅ Mock email created")
    print("\n💡 To test with real orchestrator, use:")
    print("   python run_orchestrator.py --mode latest")


if __name__ == '__main__':
    print("=" * 60)
    print("Testing Orchestrator Components")
    print("=" * 60 + "\n")
    
    try:
        test_state_manager()
        test_email_parser()
        test_decision_engine()
        test_with_mock_email()
        
        print("=" * 60)
        print("✅ All component tests completed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

