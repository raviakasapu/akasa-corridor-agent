"""Akasa Corridor Agent Backend - FastAPI Application."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Load .env file from project root
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from app.core.config import settings
from app.core.logging import setup_logging

# SDK Agent (using Composable Agent Framework)
try:
    import agent_framework
    AGENT_FRAMEWORK_VERSION = getattr(agent_framework, "__version__", "unknown")
    from app.sdk_agent.api import router as sdk_agent_router, websocket_agent
    SDK_AGENT_AVAILABLE = True
except ImportError as e:
    SDK_AGENT_AVAILABLE = False
    AGENT_FRAMEWORK_VERSION = None
    logging.warning(f"[STARTUP] SDK Agent not available: {e}")

# Configure logging
setup_logging(level=logging.INFO, use_rich=True)

# Log startup configuration
logging.info(f"[STARTUP] LLM Gateway: {settings.llm_gateway}")
logging.info(f"[STARTUP] Coordinator model: {settings.coordinator_model}")
logging.info(f"[STARTUP] Worker model: {settings.worker_model}")

if SDK_AGENT_AVAILABLE:
    logging.info(f"[STARTUP] agent_framework version: {AGENT_FRAMEWORK_VERSION}")

app = FastAPI(
    title="Akasa Corridor Agent",
    description="Multi-agent drone corridor management system with geocode-addressed corridors",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Agent REST routes at /api/v1
if SDK_AGENT_AVAILABLE:
    app.include_router(sdk_agent_router)
    logging.info(f"[STARTUP] Agent enabled (Framework v{AGENT_FRAMEWORK_VERSION})")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "agent_framework": AGENT_FRAMEWORK_VERSION if SDK_AGENT_AVAILABLE else None,
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Akasa Corridor Agent",
        "version": "1.0.0",
        "agent_framework": AGENT_FRAMEWORK_VERSION if SDK_AGENT_AVAILABLE else None,
        "docs": "/docs" if settings.debug else None,
        "endpoints": {
            "ws": "/ws/agent" if SDK_AGENT_AVAILABLE else None,
            "stream": "/api/v1/execute/stream" if SDK_AGENT_AVAILABLE else None,
            "sync": "/api/v1/execute" if SDK_AGENT_AVAILABLE else None,
        },
    }


# WebSocket endpoint for corridor agent
@app.websocket("/ws/agent")
async def ws_agent(websocket: WebSocket):
    """WebSocket endpoint for real-time agent execution.

    Expected message format:
    {
        "task": "Natural language command",
        "job_id": "your-job-id",
        "config_path": "optional config path"
    }
    """
    if not SDK_AGENT_AVAILABLE:
        await websocket.accept()
        await websocket.send_json({
            "event": "error",
            "data": {"message": "SDK Agent not available. Check server logs."},
        })
        await websocket.close()
        return
    await websocket_agent(websocket)
