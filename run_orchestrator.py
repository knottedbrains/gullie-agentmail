#!/usr/bin/env python3
"""
Run the Gullie Orchestrator Server
"""

import uvicorn
import os

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')
    
    print(f"🚀 Starting Gullie Orchestrator API server")
    print(f"📡 Server: http://{host}:{port}")
    print(f"📚 API docs: http://{host}:{port}/docs")
    print(f"🔗 Webhook: http://{host}:{port}/webhook/gmail")
    
    uvicorn.run("server:app", host=host, port=port, reload=True)
