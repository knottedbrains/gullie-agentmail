#!/usr/bin/env python3
"""
Email Parser - Extract structured information from email content
"""

import json
import os
import re
from typing import Dict, Optional, Tuple, Any

from openai import OpenAI

from send_email import load_openai_api_key, fetch_thread_messages, fetch_email_by_id


class EmailParser:
    """Parses emails and extracts structured information using LLM."""
    
    def __init__(self, gmail_service=None):
        api_key = load_openai_api_key()
        if not os.getenv('OPENAI_API_KEY'):
            os.environ['OPENAI_API_KEY'] = api_key
        self.client = OpenAI()
        self.service = gmail_service  # Gmail service for fetching thread details
    
    def parse_email(self, email_dict: Dict) -> Dict[str, Any]:
        """Parse Gmail message format into structured data."""
        return {
            'id': email_dict.get('id'),
            'from': email_dict.get('from', ''),
            'subject': email_dict.get('subject', ''),
            'body': email_dict.get('body', ''),
            'snippet': email_dict.get('snippet', '')
        }
    
    def extract_email_address(self, text: str) -> Optional[str]:
        """Extract email address from text (for sender identification)."""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        matches = re.findall(email_pattern, text)
        return matches[0] if matches else None
    
    def identify_sender(self, email: Dict) -> str:
        """Determine if sender is employee/vendor/unknown."""
        from_field = email.get('from', '').lower()
        
        # Extract email address from "Name <email@domain.com>" format
        email_addr = self.extract_email_address(from_field)
        if not email_addr:
            return "unknown"
        
        # Simple heuristic: could be enhanced with a known list
        # For now, assume any email is a potential employee
        # In production, you'd maintain a list of known vendors
        return "employee"
    
    def extract_fields(self, text: str, context: str, fields: Optional[Dict[str, str]] = None) -> Dict[str, Optional[Any]]:
        """Use LLM to extract fields from text based on context.
        
        The context determines what fields to look for, and the text provides the actual values.
        
        Args:
            text: The text to extract field values from
            context: Context that describes what fields/information we're looking for.
                     This could be a conversation summary, milestone description, or field definitions.
            fields: Optional explicit field definitions. If provided, these will be used.
                    If None, fields will be inferred from the context.
                    Example: {
                        "pickup_address": "pickup address including street, city, state, zip",
                        "pickup_date": "pickup date in YYYY-MM-DD format"
                    }
        
        Returns:
            Dictionary with extracted field values (None if not found)
        """
        if not context:
            print("⚠️  No context provided for field extraction")
            return {}
        
        # Step 1: Determine what fields to extract from context
        if fields:
            # Use explicitly provided fields
            field_descriptions = []
            for field_name, field_desc in fields.items():
                field_descriptions.append(f"- '{field_name}': {field_desc}")
            fields_list = "\n".join(field_descriptions)
            field_names = list(fields.keys())
        else:
            # Infer fields from context
            inference_prompt = (
                f"Based on the following context, identify what specific fields or pieces of information "
                f"need to be extracted from user responses. "
                f"Return a JSON object where each key is a field name and each value is a description of what that field represents.\n\n"
                f"Context:\n{context[:2000]}\n\n"
                f"Example output format:\n"
                f'{{"pickup_address": "pickup address including street, city, state, zip", "pickup_date": "pickup date"}}\n\n'
                f"Only include fields that are relevant to the context. Return only valid JSON."
            )
            
            try:
                inference_response = self.client.responses.create(
                    model="gpt-4o-mini",
                    input=inference_prompt
                )
                
                inference_text = inference_response.output[0].content[0].text.strip()
                
                # Extract JSON from inference response
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', inference_text, re.DOTALL)
                if json_match:
                    fields = json.loads(json_match.group())
                    field_names = list(fields.keys())
                    field_descriptions = [f"- '{k}': {v}" for k, v in fields.items()]
                    fields_list = "\n".join(field_descriptions)
                    print(f"📋 Inferred {len(field_names)} fields from context: {', '.join(field_names)}")
                else:
                    print("⚠️  Could not infer fields from context, returning empty result")
                    return {}
            except Exception as e:
                print(f"⚠️  Error inferring fields from context: {e}")
                return {}
        
        # Step 2: Extract the field values from the text
        prompt = (
            f"Extract the following fields from the text below. "
            f"Return a JSON object with these exact keys: {', '.join(field_names)}.\n\n"
            f"Fields to extract:\n{fields_list}\n\n"
            f"Context (for reference):\n{context[:1000]}\n\n"
            f"If a field is not found in the text, use null for that field.\n"
            f"Be precise and extract only information that is explicitly mentioned or clearly implied in the text.\n\n"
            f"Text to extract from:\n{text[:2000]}"
        )
        
        try:
            response = self.client.responses.create(
                model="gpt-4o-mini",
                input=prompt
            )
            
            result_text = response.output[0].content[0].text.strip()
            
            # Try to extract JSON from the response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                # Return only the requested fields, with None for missing ones
                return {field: result.get(field) for field in field_names}
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parsing JSON from LLM response: {e}")
            print(f"   Response text: {result_text[:200]}")
        except Exception as e:
            print(f"⚠️  Error extracting fields: {e}")
        
        # Return None for all fields if extraction failed
        return {field: None for field in field_names}
    
    def extract_addresses_and_dates(self, text: str, context: str = "") -> Dict[str, Optional[str]]:
        """Use LLM to extract pickup and delivery addresses from text.
        
        This is a convenience wrapper around extract_fields() for backward compatibility.
        If context is provided, it will be used to infer fields. Otherwise, default fields are used.
        """
        # If context is provided, let it infer fields. Otherwise use default fields.
        if context:
            return self.extract_fields(text, context)
        else:
            # Default fields for backward compatibility
            fields = {
                "pickup_address": "pickup address including street, city, state, and zip code if available",
                "pickup_date": "pickup date in YYYY-MM-DD format or any date format mentioned",
                "delivery_address": "delivery address including street, city, state, and zip code if available",
                "needs_box": "yes or no",
                "needs_packing_help": "yes or no",
                "insurance_opted_in": "yes or no"
            }
            
            return self.extract_fields(text, "Extract pickup and delivery addresses and pickup date", fields)
    
    def extract_yes_no_response(self, text: str, question_type: str) -> Optional[bool]:
        """Extract boolean answer from text for yes/no questions."""
        # Normalize text
        text_lower = text.lower().strip()
        
        # Common yes patterns
        yes_patterns = [
            r'\byes\b', r'\byeah\b', r'\byep\b', r'\bsure\b', r'\bok\b', r'\bokay\b',
            r'\bdefinitely\b', r'\babsolutely\b', r'\bof course\b', r'\bi do\b',
            r'\bi need\b', r'\bplease\b', r'\bwould like\b'
        ]
        
        # Common no patterns
        no_patterns = [
            r'\bno\b', r'\bnope\b', r'\bnot\b', r'\bdon\'?t\b', r'\bdo not\b',
            r'\bno thanks\b', r'\bno thank you\b', r'\bi don\'?t\b', r'\bi do not\b',
            r'\bunnecessary\b', r'\bnot needed\b'
        ]
        
        # Check for explicit yes/no
        for pattern in yes_patterns:
            if re.search(pattern, text_lower):
                return True
        
        for pattern in no_patterns:
            if re.search(pattern, text_lower):
                return False
        
        # If no clear pattern, use LLM
        prompt = (
            f"The user was asked: '{question_type}'\n"
            f"Their response was: '{text[:500]}'\n\n"
            "Determine if this is a YES or NO answer. "
            "Respond with only 'yes' or 'no'."
        )
        
        try:
            response = self.client.responses.create(
                model="gpt-4o-mini",
                input=prompt
            )
            
            result_text = response.output[0].content[0].text.strip().lower()
            if 'yes' in result_text:
                return True
            elif 'no' in result_text:
                return False
        except Exception as e:
            print(f"⚠️  Error extracting yes/no response: {e}")
        
        return None
    
    def extract_intent(self, text: str) -> str:
        """Use LLM to understand email intent."""
        prompt = (
            "Classify the intent of this email into one of these categories:\n"
            "- 'answer': Responding to questions with information\n"
            "- 'question': Asking a question\n"
            "- 'unrelated': Not related to the moving service request\n"
            "- 'greeting': Initial greeting or introduction\n\n"
            f"Email text: {text[:1000]}\n\n"
            "Respond with only the category name."
        )
        
        try:
            response = self.client.responses.create(
                model="gpt-4o-mini",
                input=prompt
            )
            
            result_text = response.output[0].content[0].text.strip().lower()
            
            if 'answer' in result_text:
                return 'answer'
            elif 'question' in result_text:
                return 'question'
            elif 'greeting' in result_text:
                return 'greeting'
            else:
                return 'unrelated'
        except Exception as e:
            print(f"⚠️  Error extracting intent: {e}")
            return 'unknown'

    def get_context_of_thread(self, thread_id: str) -> str:
        """Get the context of a thread by fetching all messages and summarizing them.
        
        Args:
            thread_id: Gmail thread ID to fetch and summarize
            
        Returns:
            Summary of the thread conversation
        """
        if not self.service:
            print("⚠️  Gmail service not available for fetching thread")
            return ""
        
        # Fetch all messages in the thread
        thread_messages = fetch_thread_messages(self.service, thread_id)
        
        if not thread_messages:
            return ""
        
        # Build conversation context from all messages
        conversation_parts = []
        for msg in thread_messages:
            # Get message details
            msg_id = msg.get('id')
            if msg_id:
                msg_details = fetch_email_by_id(self.service, msg_id)
                if msg_details:
                    from_field = msg_details.get('from', 'Unknown')
                    subject = msg_details.get('subject', 'No Subject')
                    body = msg_details.get('body', '')[:500]  # Limit body length
                    conversation_parts.append(f"From: {from_field}\nSubject: {subject}\nBody: {body}")
        
        conversation_text = "\n\n---\n\n".join(conversation_parts)
        
        prompt = (
            "You are an expert in summarizing email threads. "
            "Provide a concise summary of this email conversation thread, "
            "highlighting the main topics, decisions made, and any action items.\n\n"
            f"Email Thread:\n{conversation_text[:4000]}\n\n"
            "Provide a clear, structured summary."
        )
        
        try: 
            response = self.client.responses.create(
                model="gpt-4o-mini",
                input=prompt
            )
            return response.output[0].content[0].text.strip()
        except Exception as e:
            print(f"⚠️  Error getting context of thread: {e}")
            return ""
    
    def extract_milestone1_data(self, text: str, context: str) -> Dict[str, any]:
        """Extract all Milestone 1 data from email text."""
        result = {
            "pickup_address": None,
            "pickup_date": None,
            "delivery_address": None,
            "needs_box": None,
            "needs_packing_help": None,
            "insurance_opted_in": None
        }
        
        # Extract addresses
        addresses = self.extract_addresses_and_dates(text, context)
        result.update(addresses)
        
        # Extract yes/no responses
        # Look for context around box, packing, insurance
        box_context = self._extract_context(text, ['box', 'boxes', 'packing box'])
        if box_context:
            result["needs_box"] = self.extract_yes_no_response(
                box_context, "Do you need boxes?"
            )
        
        packing_context = self._extract_context(text, ['packing', 'help packing', 'packing help'])
        if packing_context:
            result["needs_packing_help"] = self.extract_yes_no_response(
                packing_context, "Do you need help packing?"
            )
        
        insurance_context = self._extract_context(text, ['insurance', 'insure', 'coverage'])
        if insurance_context:
            result["insurance_opted_in"] = self.extract_yes_no_response(
                insurance_context, "Do you want to opt-in for insurance?"
            )
        
        return result
    
    def _extract_context(self, text: str, keywords: list) -> Optional[str]:
        """Extract context around keywords (sentence or nearby sentences)."""
        text_lower = text.lower()
        for keyword in keywords:
            if keyword.lower() in text_lower:
                # Find the sentence containing the keyword
                sentences = re.split(r'[.!?]\s+', text)
                for sentence in sentences:
                    if keyword.lower() in sentence.lower():
                        return sentence
                # If no sentence boundary, return a window around the keyword
                idx = text_lower.find(keyword.lower())
                if idx >= 0:
                    start = max(0, idx - 100)
                    end = min(len(text), idx + len(keyword) + 100)
                    return text[start:end]
        return None
    
    def is_move_initiation_request(self, email_text: str) -> bool:
        """Use LLM to determine if email is about initiating a move/relocation."""
        prompt = (
            "Determine if this email is a request to initiate a move or relocation for an employee. "
            "Look for keywords like: move, relocate, relocation, employee moving, moving request, etc. "
            "The email should be from an employer/company requesting moving services for an employee.\n\n"
            f"Email text: {email_text[:2000]}\n\n"
            "Respond with only 'yes' or 'no'."
        )
        
        try:
            response = self.client.responses.create(
                model="gpt-4o-mini",
                input=prompt
            )
            
            result_text = response.output[0].content[0].text.strip().lower()
            return 'yes' in result_text
        except Exception as e:
            print(f"⚠️  Error checking move initiation: {e}")
            # Fallback: check for common keywords
            text_lower = email_text.lower()
            keywords = ['move', 'relocate', 'relocation', 'moving', 'employee move']
            return any(keyword in text_lower for keyword in keywords)
    
    def is_relevant_to_shipping_moving(self, email_text: str, employee_email: Optional[str] = None, company_name: Optional[str] = None) -> bool:
        """Use LLM to determine if email is relevant to shipping/moving for specific employee and company."""
        context_parts = []
        if employee_email:
            context_parts.append(f"employee email: {employee_email}")
        if company_name:
            context_parts.append(f"company: {company_name}")
        
        context = "\n".join(context_parts) if context_parts else "general shipping/moving context"
        
        prompt = (
            f"Determine if this email is relevant to shipping, moving, or relocation services. "
            f"Context: {context}\n\n"
            f"The email should be related to:\n"
            f"- Moving or shipping services\n"
            f"- Relocation requests\n"
            f"- Moving logistics\n"
            f"- Shipping quotes or updates\n"
            f"- Moving-related communications\n\n"
            f"Email text: {email_text[:2000]}\n\n"
            f"Respond with only 'yes' if relevant, or 'no' if not relevant."
        )
        
        try:
            response = self.client.responses.create(
                model="gpt-4o-mini",
                input=prompt
            )
            
            result_text = response.output[0].content[0].text.strip().lower()
            return 'yes' in result_text
        except Exception as e:
            print(f"⚠️  Error checking email relevance: {e}")
            # Fallback: check for common keywords
            text_lower = email_text.lower()
            keywords = ['move', 'relocate', 'relocation', 'moving', 'shipping', 'shipment', 'delivery', 'pickup']
            return any(keyword in text_lower for keyword in keywords)
    
    def extract_employee_email_from_request(self, email_text: str) -> Optional[str]:
        """Extract employee email address from a move initiation request."""
        # Look for email patterns in the text
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, email_text)
        
        # Filter out common sender emails (like cluely@gmail.com, gullie-agent@gmail.com)
        excluded_domains = ['gullie-agent@gmail.com', 'cluely@gmail.com', 'gmail.com']
        for email in emails:
            email_lower = email.lower()
            if not any(excluded in email_lower for excluded in excluded_domains):
                # Use LLM to confirm this is the employee email
                prompt = (
                    f"From this move request email, identify the employee's email address. "
                    f"The employee email should be mentioned in contact info section.\n\n"
                    f"Email text: {email_text[:1500]}\n\n"
                    f"Found emails: {', '.join(emails)}\n\n"
                    "Respond with only the employee email address, or 'none' if not found."
                )
                
                try:
                    response = self.client.responses.create(
                        model="gpt-4o-mini",
                        input=prompt
                    )
                    
                    result_text = response.output[0].content[0].text.strip()
                    # Check if result is an email
                    if '@' in result_text and result_text.lower() != 'none':
                        return result_text.strip()
                except Exception as e:
                    print(f"⚠️  Error extracting employee email: {e}")
        
        # Fallback: return first non-excluded email
        for email in emails:
            email_lower = email.lower()
            if not any(excluded in email_lower for excluded in excluded_domains):
                return email
        
        return None

