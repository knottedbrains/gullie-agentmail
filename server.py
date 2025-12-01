#!/usr/bin/env python3
"""
FastAPI Server - REST API for Gullie Email Orchestrator
"""

import asyncio
import json
import os
from typing import Optional, Set
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from googleapiclient.discovery import build
from pydantic import BaseModel

from orchestrator import Orchestrator
from email_parser import EmailParser
from send_email import get_credentials, fetch_email_by_id, fetch_recent_emails


# Configuration from environment variables
EMPLOYEE_EMAIL_FILTER = os.getenv('EMPLOYEE_EMAIL_FILTER', 'ninan980805@gmail.com')  # Optional: filter for specific employee
COMPANY_NAME_FILTER = os.getenv('COMPANY_NAME_FILTER', 'cluely')  # Optional: filter for specific company
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', 60))  # Poll every 60 seconds
MAX_EMAILS_PER_POLL = int(os.getenv('MAX_EMAILS_PER_POLL', 5))  # Check last 5 emails

# Global services
orchestrator: Optional[Orchestrator] = None
email_parser: Optional[EmailParser] = None
gmail_service = None
processed_email_ids: Set[str] = set()  # Track processed emails


# Request/Response models
class InitiateCaseRequest(BaseModel):
    employee_email: str


class ProcessEmailRequest(BaseModel):
    message_id: Optional[str] = None


async def poll_emails_task():
    """Background task that polls emails every minute."""
    global processed_email_ids
    
    while True:
        try:
            await asyncio.sleep(POLL_INTERVAL)
            
            if not gmail_service or not orchestrator or not email_parser:
                print("⚠️  Services not initialized, skipping poll")
                continue
            
            print(f"\n🔄 Polling for new emails (checking last {MAX_EMAILS_PER_POLL} emails)...")
            
            emails = fetch_recent_emails(gmail_service, max_results=MAX_EMAILS_PER_POLL)
            
            if not emails:
                print("📭 No emails found")
                continue
            
            for email in emails:
                email_id = email.get('id')
                
                # Skip if already processed
                if email_id in processed_email_ids:
                    continue
                
                print(f"\n📧 Processing email: {email.get('subject', 'No Subject')}")
                print(f"   From: {email.get('from', 'Unknown')}")
                
                # Check if email is relevant using LLM filter
                email_text = f"{email.get('subject', '')}\n\n{email.get('body', '')}"
                
                employee_filter = EMPLOYEE_EMAIL_FILTER if EMPLOYEE_EMAIL_FILTER else None
                company_filter = COMPANY_NAME_FILTER if COMPANY_NAME_FILTER else None
                
                is_relevant = email_parser.is_relevant_to_shipping_moving(
                    email_text,
                    employee_email=employee_filter,
                    company_name=company_filter
                )
                
                if not is_relevant:
                    print("⏭️  Email not relevant to shipping/moving, skipping...")
                    processed_email_ids.add(email_id)  # Mark as processed to avoid re-checking
                    continue
                

                print("✅ Email is relevant, processing...")
                
                # Double-check if email has been processed (in case it was processed between checks)
                if email_id in processed_email_ids:
                    print("⏭️  Email already processed, skipping...")
                    continue
                
                # Process as regular email
                success = orchestrator.process_incoming_email(email)
                if success:
                    processed_email_ids.add(email_id)
                    print("✅ Email processed successfully")
                else:
                    print("⚠️  Email processing had issues")
                        
        except Exception as e:
            print(f"❌ Error during email polling: {e}")
            import traceback
            traceback.print_exc()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown."""
    global orchestrator, email_parser, gmail_service
    
    # Startup
    try:
        print("🔐 Authenticating with Gmail...")
        creds = get_credentials()
        gmail_service = build('gmail', 'v1', credentials=creds)
        print("✅ Authenticated successfully")
        
        orchestrator = Orchestrator(gmail_service)
        email_parser = EmailParser(gmail_service=gmail_service)
        print("✅ Services initialized")
        
        # Print configuration
        print(f"\n📋 Configuration:")
        print(f"   Poll interval: {POLL_INTERVAL} seconds")
        print(f"   Emails per poll: {MAX_EMAILS_PER_POLL}")
        if EMPLOYEE_EMAIL_FILTER:
            print(f"   Employee filter: {EMPLOYEE_EMAIL_FILTER}")
        if COMPANY_NAME_FILTER:
            print(f"   Company filter: {COMPANY_NAME_FILTER}")
        print()
        
        # Start background polling task
        poll_task = asyncio.create_task(poll_emails_task())
        print("🔄 Email polling started")
        
    except Exception as e:
        print(f"❌ Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")


app = FastAPI(
    title="Gullie Email Orchestrator API",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "gullie-orchestrator",
        "gmail_connected": gmail_service is not None,
        "processed_emails": len(processed_email_ids),
        "poll_interval": POLL_INTERVAL,
        "max_emails_per_poll": MAX_EMAILS_PER_POLL,
        "employee_filter": EMPLOYEE_EMAIL_FILTER or "none",
        "company_filter": COMPANY_NAME_FILTER or "none"
    }


@app.post("/api/v1/initiate")
async def initiate_case_endpoint(request: InitiateCaseRequest):
    """Manually initiate a new case for an employee."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    try:
        success = orchestrator.initiate_case(request.employee_email)
        if success:
            return {
                "status": "success",
                "message": f"Case initiated for {request.employee_email}",
                "employee_email": request.employee_email
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initiate case for {request.employee_email}"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/process/email")
async def process_email_endpoint(request: ProcessEmailRequest):
    """Process a specific email by message ID, or all recent emails if no ID provided."""
    if not orchestrator or not gmail_service:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    try:
        if request.message_id:
            # Process single email by ID
            email = fetch_email_by_id(gmail_service, request.message_id)
            if not email:
                raise HTTPException(
                    status_code=404,
                    detail=f"Email {request.message_id} not found"
                )
            emails_to_process = [email]
        else:
            # Process all recent emails
            emails_to_process = fetch_recent_emails(gmail_service, max_results=MAX_EMAILS_PER_POLL)
            if not emails_to_process:
                raise HTTPException(status_code=404, detail="No emails found")
        
        employee_filter = EMPLOYEE_EMAIL_FILTER if EMPLOYEE_EMAIL_FILTER else None
        company_filter = COMPANY_NAME_FILTER if COMPANY_NAME_FILTER else None
        
        results = []
        
        for email in emails_to_process:
            email_id = email.get('id')
            email_result = {
                "message_id": email_id,
                "subject": email.get('subject', 'No Subject'),
                "from": email.get('from', 'Unknown')
            }
            
            # Check if email is relevant using LLM filter
            email_text = f"{email.get('subject', '')}\n\n{email.get('body', '')}"
            
            is_relevant = email_parser.is_relevant_to_shipping_moving(
                email_text,
                employee_email=employee_filter,
                company_name=company_filter
            )
            
            if not is_relevant:
                email_result.update({
                    "status": "skipped",
                    "action": "filtered_out",
                    "message": "Email not relevant to shipping/moving based on filters"
                })
                results.append(email_result)
                continue
            else:
                # Process as regular email
                success = orchestrator.process_incoming_email(email)
                email_result.update({
                    "status": "success" if success else "partial",
                    "action": "processed_email",
                    "message": "Email processed successfully" if success else "Email processing had issues"
                })
            
            results.append(email_result)
        
        return {
            "status": "success",
            "processed_count": len(results),
            "results": results
        }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/state")
async def get_state():
    """Get current state of all cases."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    try:
        all_cases = orchestrator.state_manager.get_all_cases()
        return {
            "status": "success",
            "cases": all_cases,
            "total_cases": len(all_cases)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/state/{employee_email}")
async def get_case_state(employee_email: str):
    """Get state for a specific employee case."""
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    try:
        case = orchestrator.state_manager.get_case(employee_email)
        if not case:
            raise HTTPException(
                status_code=404,
                detail=f"Case not found for {employee_email}"
            )
        return {
            "status": "success",
            "case": case
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')
    
    print(f"🚀 Starting Gullie Orchestrator API server")
    print(f"📡 Server: http://{host}:{port}")
    print(f"📚 API docs: http://{host}:{port}/docs")
    print(f"\n💡 Configuration via environment variables:")
    print(f"   EMPLOYEE_EMAIL_FILTER - Filter emails for specific employee")
    print(f"   COMPANY_NAME_FILTER - Filter emails for specific company")
    print(f"   POLL_INTERVAL - Poll interval in seconds (default: 60)")
    print(f"   MAX_EMAILS_PER_POLL - Number of emails to check per poll (default: 5)")
    
    uvicorn.run(app, host=host, port=port)

