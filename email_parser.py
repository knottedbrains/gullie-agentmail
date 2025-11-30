#!/usr/bin/env python3
"""
Email Parser - Extract structured information from email content
"""

import json
import os
import re
from typing import Dict, Optional, Tuple, Any

from openai import OpenAI

from send_email import load_openai_api_key


class EmailParser:
    """Parses emails and extracts structured information using LLM."""
    
    def __init__(self):
        api_key = load_openai_api_key()
        if not os.getenv('OPENAI_API_KEY'):
            os.environ['OPENAI_API_KEY'] = api_key
        self.client = OpenAI()
    
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
    
    def extract_addresses(self, text: str) -> Dict[str, Optional[str]]:
        """Use LLM to extract pickup and delivery addresses from text."""
        prompt = (
            "Extract pickup and delivery addresses from the following text. "
            "Return a JSON object with 'pickup_address' and 'delivery_address' keys. "
            "If an address is not found, use null. "
            "Addresses should be complete and include street, city, state, and zip code if available.\n\n"
            f"Text: {text[:2000]}"
        )
        
        try:
            response = self.client.responses.create(
                model="gpt-4o-mini",
                input=prompt
            )
            
            result_text = response.output[0].content[0].text.strip()
            
            # Try to extract JSON from the response
            json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "pickup_address": result.get("pickup_address"),
                    "delivery_address": result.get("delivery_address")
                }
        except Exception as e:
            print(f"⚠️  Error extracting addresses: {e}")
        
        return {"pickup_address": None, "delivery_address": None}
    
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
    
    def extract_milestone1_data(self, text: str) -> Dict[str, any]:
        """Extract all Milestone 1 data from email text."""
        result = {
            "pickup_address": None,
            "delivery_address": None,
            "needs_box": None,
            "needs_packing_help": None,
            "insurance_opted_in": None
        }
        
        # Extract addresses
        addresses = self.extract_addresses(text)
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

