#!/usr/bin/env python3
"""
FastAPI Server - REST API for Gullie Email Orchestrator
"""

import base64
import json
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from googleapiclient.discovery import build
from pydantic import BaseModel

from orchestrator import Orchestrator
from email_parser import EmailParser
from send_email import get_credentials, fetch_email_by_id, fetch_latest_email


app = FastAPI(title="Gullie Email Orchestrator API", version="1.0.0")

# Global services (initialized on startup)
orchestrator: Optional[Orchestrator] = None
email_parser: Optional[EmailParser] = None
gmail_service = None


# Request/Response models
class InitiateCaseRequest(BaseModel):
    employee_email: str


class ProcessEmailRequest(BaseModel):
    message_id: Optional[str] = None


class WebhookNotification(BaseModel):
    message: Optional[dict] = None
    historyId: Optional[str] = None
    messageId: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on server startup."""
    global orchestrator, email_parser, gmail_service
    
    try:
        print("🔐 Authenticating with Gmail...")
        creds = get_credentials()
        gmail_service = build('gmail', 'v1', credentials=creds)
        print("✅ Authenticated successfully")
        
        orchestrator = Orchestrator(gmail_service)
        email_parser = EmailParser()
        print("✅ Services initialized")
    except Exception as e:
        print(f"❌ Failed to initialize services: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "gullie-orchestrator",
        "gmail_connected": gmail_service is not None
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
    """Process a specific email by message ID, or latest email if no ID provided."""
    if not orchestrator or not gmail_service:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    try:
        if request.message_id:
            email = fetch_email_by_id(gmail_service, request.message_id)
            if not email:
                raise HTTPException(
                    status_code=404,
                    detail=f"Email {request.message_id} not found"
                )
        else:
            email = fetch_latest_email(gmail_service)
            if not email:
                raise HTTPException(status_code=404, detail="No emails found")
        
        # Check if it's a move initiation request
        email_text = f"{email.get('subject', '')}\n\n{email.get('body', '')}"
        
        if email_parser.is_move_initiation_request(email_text):
            employee_email = email_parser.extract_employee_email_from_request(email_text)
            if employee_email:
                success = orchestrator.initiate_case(employee_email)
                return {
                    "status": "success",
                    "action": "initiated_case",
                    "employee_email": employee_email,
                    "message": f"Move initiation detected and case started for {employee_email}"
                }
            else:
                return {
                    "status": "partial",
                    "action": "detected_initiation",
                    "message": "Move initiation detected but could not extract employee email"
                }
        else:
            # Process as regular email
            success = orchestrator.process_incoming_email(email)
            return {
                "status": "success" if success else "partial",
                "action": "processed_email",
                "message_id": email.get('id'),
                "message": "Email processed successfully" if success else "Email processing had issues"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/gmail")
async def gmail_webhook(notification: WebhookNotification):
    """Handle Gmail push notification webhook."""
    if not orchestrator or not gmail_service:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    try:
        message_id = None
        
        # Handle different notification formats
        if notification.message and 'data' in notification.message:
            # Decode base64 message ID
            message_id = base64.urlsafe_b64decode(
                notification.message['data']
            ).decode('utf-8')
        elif notification.messageId:
            message_id = notification.messageId
        elif notification.historyId:
            # History notification - process latest email
            email = fetch_latest_email(gmail_service)
            if email:
                message_id = email.get('id')
        
        if message_id:
            email = fetch_email_by_id(gmail_service, message_id)
            if email:
                email_text = f"{email.get('subject', '')}\n\n{email.get('body', '')}"
                
                if email_parser.is_move_initiation_request(email_text):
                    employee_email = email_parser.extract_employee_email_from_request(email_text)
                    if employee_email:
                        orchestrator.initiate_case(employee_email)
                        return {
                            "status": "success",
                            "action": "initiated_case",
                            "employee_email": employee_email
                        }
                else:
                    orchestrator.process_incoming_email(email)
                    return {
                        "status": "success",
                        "action": "processed_email"
                    }
        
        return {"status": "success", "message": "Notification received"}
        
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/webhook/gmail")
async def webhook_verification(request: Request):
    """Handle webhook verification (Gmail requires this for initial setup)."""
    challenge = request.query_params.get('challenge')
    if challenge:
        print(f"✅ Webhook verification challenge: {challenge}")
        return challenge
    return {"status": "ok"}


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
    print(f"🔗 Webhook: http://{host}:{port}/webhook/gmail")
    
    uvicorn.run(app, host=host, port=port)

