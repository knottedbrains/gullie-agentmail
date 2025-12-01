#!/usr/bin/env python3
"""
Email Templates - Generate structured email content for each milestone action
"""

from typing import List


def get_milestone1_initial_request() -> tuple[str, str]:
    """First email asking for all Milestone 1 information."""
    subject = "Moving Service Request - Information Needed"
    
    body = """Hello!

I'm Gullie, your moving service assistant. To help you with your move, I need to collect some information:

1. **Pickup Address**: Where should we pick up your belongings?
2. **Pickup Date**: When should we pick up your belongings?
2. **Delivery Address**: Where should we deliver your belongings?
3. **Boxes**: Do you need moving boxes?
4. **Packing Help**: Do you need help with packing?
5. **Insurance**: Would you like to opt-in for moving insurance?

Please reply to this email with all the information above. You can provide it in any format that's convenient for you.

Thank you!
Gullie"""
    
    return subject, body


def get_milestone1_followup(missing_fields: List[str]) -> tuple[str, str]:
    """Follow-up email for missing information."""
    subject = "Moving Service Request - Additional Information Needed"
    
    # Create a friendly list of missing items
    field_descriptions = {
        "pickup_address": "pickup address",
        "pickup_date": "pickup date",
        "delivery_address": "delivery address",
        "needs_box": "whether you need boxes",
        "needs_packing_help": "whether you need help with packing",
        "insurance_opted_in": "whether you want to opt-in for insurance"
    }
    
    missing_list = [field_descriptions.get(field, field) for field in missing_fields]
    
    if len(missing_list) == 1:
        items_text = missing_list[0]
    elif len(missing_list) == 2:
        items_text = f"{missing_list[0]} and {missing_list[1]}"
    else:
        items_text = ", ".join(missing_list[:-1]) + f", and {missing_list[-1]}"
    
    body = f"""Hello!

Thank you for your response! I still need a bit more information to proceed:

I'm missing: {items_text}

Please reply with this information and I'll be able to move forward with your request.

Thank you!
Gullie"""
    
    return subject, body


def get_milestone1_completion_confirmation() -> tuple[str, str]:
    """Confirmation email when all Milestone 1 data is collected."""
    subject = "Moving Service Request - Information Received"
    
    body = """Hello!

Perfect! I've received all the information I need for your moving service request. 

I'll now proceed to coordinate with our moving vendors to get you a quote. You'll hear from me soon with the next steps.

Thank you for providing all the details!
Gullie"""
    
    return subject, body


def get_clarification_request(unclear_field: str) -> tuple[str, str]:
    """Request clarification when a response is unclear."""
    subject = "Moving Service Request - Need Clarification"
    
    field_questions = {
        "pickup_address": "your pickup address",
        "pickup_date": "your pickup date",
        "delivery_address": "your delivery address",
        "needs_box": "whether you need boxes (yes or no)",
        "needs_packing_help": "whether you need help with packing (yes or no)",
        "insurance_opted_in": "whether you want to opt-in for insurance (yes or no)"
    }
    
    question = field_questions.get(unclear_field, unclear_field)
    
    body = f"""Hello!

I received your message, but I need a bit of clarification:

Could you please provide {question}?

A simple yes/no or the specific information would be great!

Thank you!
Gullie"""
    
    return subject, body

