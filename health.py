#!/usr/bin/env python3
"""
FastAPI Health Server for Penny Summarizer
Runs pennysum.py in background and sends health pings
"""

import asyncio
import subprocess
import sys
import threading
import time
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import requests
import uvicorn

app = FastAPI(title="Penny Summarizer Health Server")

# Configuration
HEALTH_PING_URL = "https://penny-sum.onrender.com"
HEALTH_PING_INTERVAL = 300  # 5 minutes in seconds

# Global state
summarizer_process = None
last_ping_time = None
last_ping_status = None


def run_summarizer():
    """Run pennysum.py as a subprocess"""
    global summarizer_process
    try:
        print(f"[{datetime.now()}] Starting pennysum.py in background...")
        summarizer_process = subprocess.Popen(
            [sys.executable, "pennysum.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        print(f"[{datetime.now()}] pennysum.py started with PID: {summarizer_process.pid}")
        
        # Monitor the process output in a separate thread
        def monitor_output():
            for line in summarizer_process.stdout:
                print(f"[SUMMARIZER] {line.strip()}")
        
        monitor_thread = threading.Thread(target=monitor_output, daemon=True)
        monitor_thread.start()
        
    except Exception as e:
        print(f"[{datetime.now()}] Error starting pennysum.py: {e}")


async def send_health_ping():
    """Send health ping to the specified URL"""
    global last_ping_time, last_ping_status
    try:
        print(f"[{datetime.now()}] Sending health ping to {HEALTH_PING_URL}")
        response = requests.get(HEALTH_PING_URL, timeout=10)
        last_ping_time = datetime.now()
        last_ping_status = response.status_code
        print(f"[{datetime.now()}] Health ping successful - Status: {response.status_code}")
        return True
    except Exception as e:
        last_ping_time = datetime.now()
        last_ping_status = "Error"
        print(f"[{datetime.now()}] Health ping failed: {e}")
        return False


async def health_ping_loop():
    """Background task to send health pings every 5 minutes"""
    while True:
        await send_health_ping()
        await asyncio.sleep(HEALTH_PING_INTERVAL)


@app.on_event("startup")
async def startup_event():
    """Start background tasks on server startup"""
    print(f"[{datetime.now()}] FastAPI server starting up...")
    
    # Start the summarizer in background
    run_summarizer()
    
    # Start health ping loop
    asyncio.create_task(health_ping_loop())
    
    print(f"[{datetime.now()}] All background tasks started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on server shutdown"""
    global summarizer_process
    print(f"[{datetime.now()}] FastAPI server shutting down...")
    
    if summarizer_process and summarizer_process.poll() is None:
        print(f"[{datetime.now()}] Terminating pennysum.py process...")
        summarizer_process.terminate()
        try:
            summarizer_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            summarizer_process.kill()
        print(f"[{datetime.now()}] pennysum.py process terminated")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Penny Summarizer Health Server",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global summarizer_process, last_ping_time, last_ping_status
    
    # Check if summarizer is running
    summarizer_running = (
        summarizer_process is not None and 
        summarizer_process.poll() is None
    )
    
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy" if summarizer_running else "unhealthy",
            "summarizer_running": summarizer_running,
            "summarizer_pid": summarizer_process.pid if summarizer_running else None,
            "last_ping_time": last_ping_time.isoformat() if last_ping_time else None,
            "last_ping_status": last_ping_status,
            "timestamp": datetime.now().isoformat()
        }
    )


@app.get("/restart-summarizer")
async def restart_summarizer():
    """Restart the summarizer process"""
    global summarizer_process
    
    # Stop existing process
    if summarizer_process and summarizer_process.poll() is None:
        print(f"[{datetime.now()}] Stopping existing pennysum.py process...")
        summarizer_process.terminate()
        try:
            summarizer_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            summarizer_process.kill()
    
    # Start new process
    run_summarizer()
    
    return {
        "status": "restarted",
        "pid": summarizer_process.pid if summarizer_process else None,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/ping-now")
async def ping_now():
    """Manually trigger a health ping"""
    success = await send_health_ping()
    return {
        "success": success,
        "last_ping_time": last_ping_time.isoformat() if last_ping_time else None,
        "last_ping_status": last_ping_status,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    print("="*60)
    print("Starting Penny Summarizer Health Server")
    print("="*60)
    uvicorn.run(app, host="0.0.0.0", port=8000)

