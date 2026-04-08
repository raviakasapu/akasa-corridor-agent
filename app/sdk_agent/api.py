"""FastAPI endpoints for the Akasa Corridor Agent.

Provides WebSocket, SSE, and synchronous REST endpoints.
Adapted from power-bi-backend-agent-v2 patterns.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent import CorridorAgent
from agent_framework.composable.agents.events import AgentEvent, AgentEventType
from .tools.simulation.engine import (
    register_tick_callback, register_alert_callback,
    register_edge_telemetry_callback, unregister_tick_callback,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Corridor Agent"])

# Track tool indices per session
_tool_index_counter: dict[str, int] = {}


def map_event_to_frontend(event: AgentEvent, job_id: str = "") -> dict:
    """Map framework AgentEvent to frontend-compatible format."""
    type_mapping = {
        AgentEventType.AGENT_START: "status",
        AgentEventType.THINKING: "thinking",
        AgentEventType.CONTENT: "content",
        AgentEventType.CONTENT_PARTIAL: "content",
        AgentEventType.TOOL_CALL: "tool_call",
        AgentEventType.TOOL_RESULT: "tool_done",
        AgentEventType.AGENT_COMPLETE: "complete",
        AgentEventType.AGENT_ERROR: "error",
        AgentEventType.TOOL_ERROR: "error",
    }

    event_type = type_mapping.get(event.type, event.type.value)
    data = event.data.copy() if event.data else {}

    if event.type == AgentEventType.AGENT_START:
        _tool_index_counter[job_id] = 0
        data = {"message": "Starting...", "display": "inline"}
    elif event.type == AgentEventType.THINKING:
        data = {
            "message": data.get("message", "Processing..."),
            "iteration": data.get("iteration", 1),
            "display": "inline",
        }
    elif event.type in (AgentEventType.CONTENT, AgentEventType.CONTENT_PARTIAL):
        text = data.get("text", "")
        data = {"text": text, "content": text}
    elif event.type == AgentEventType.TOOL_CALL:
        current_index = _tool_index_counter.get(job_id, 0)
        _tool_index_counter[job_id] = current_index + 1
        data = {
            "tool": data.get("tool", ""),
            "args": data.get("input", {}),
            "tool_index": current_index + 1,
            "tool_id": data.get("tool_id", ""),
        }
    elif event.type == AgentEventType.TOOL_RESULT:
        result = data.get("result", {})
        summary = result.get("summary", str(result)) if isinstance(result, dict) else str(result)
        data = {
            "tool": data.get("tool", ""),
            "success": data.get("success", True),
            "summary": summary,
            "result": result,
            "tool_id": data.get("tool_id", ""),
        }
    elif event.type == AgentEventType.AGENT_COMPLETE:
        usage = data.get("usage", {})
        data = {
            "message": "Complete",
            "duration_s": data.get("duration_s", 0),
            "iterations": data.get("iterations", 0),
            "tool_calls": data.get("tool_calls", 0),
            "usage": {
                "input_tokens": usage.get("total_input_tokens", 0),
                "output_tokens": usage.get("total_output_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            } if usage else None,
        }
    elif event.type in (AgentEventType.AGENT_ERROR, AgentEventType.TOOL_ERROR):
        data = {"message": data.get("error", str(data))}

    return {
        "event": event_type,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }


# ============================================================================
# Request/Response Models
# ============================================================================

class ExecuteRequest(BaseModel):
    """Request model for agent execution."""
    job_id: str
    message: str
    model: Optional[str] = None
    max_iterations: Optional[int] = 40


class ExecuteResponse(BaseModel):
    """Response model for synchronous execution."""
    content: str
    duration_s: float
    tool_calls: int


class MissionRequest(BaseModel):
    """Request model for a full mission execution."""
    job_id: str
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    corridor_name: str = "Mission Corridor"
    resolution: int = 10
    monitor_cycles: int = 8


# ============================================================================
# WebSocket Handler
# ============================================================================

async def websocket_agent(websocket: WebSocket):
    """WebSocket endpoint for real-time agent streaming."""
    await websocket.accept()
    logger.info("[Corridor Agent WS] Client connected")

    await websocket.send_json({
        "event": "connected",
        "data": {"agent": "akasa-corridor-agent", "version": "1.0.0"},
        "timestamp": int(time.time() * 1000),
    })

    current_agent: Optional[CorridorAgent] = None

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action", "execute")

            if action == "set_context":
                job_id = data.get("job_id", "default")
                mode = data.get("mode", "single")
                current_agent = CorridorAgent(job_id=job_id, mode=mode)
                await websocket.send_json({
                    "event": "context_set",
                    "data": {"job_id": job_id, "mode": mode},
                    "timestamp": int(time.time() * 1000),
                })

            elif action == "execute":
                message = data.get("message") or data.get("task", "")
                job_id = data.get("job_id", "default")

                if not message:
                    await websocket.send_json({
                        "event": "error",
                        "data": {"message": "No message provided."},
                        "timestamp": int(time.time() * 1000),
                    })
                    continue

                if current_agent is None:
                    mode = data.get("mode", "single")
                    current_agent = CorridorAgent(job_id=job_id, mode=mode)

                async for event in current_agent.run(message):
                    frontend_event = map_event_to_frontend(event, job_id)
                    await websocket.send_json(frontend_event)

                    # When start_simulation completes, register tick callback
                    # to push real-time position updates to the frontend
                    if event.type == AgentEventType.TOOL_RESULT:
                        tool_name = event.data.get("tool", "")
                        result_data = event.data.get("result", {})

                        if tool_name == "start_simulation" and isinstance(result_data, dict):
                            flight_id = result_data.get("flight_id", "")
                            if flight_id:
                                # Register tick callback (drone position updates)
                                async def make_tick_sender(ws=websocket):
                                    async def send_tick(state: dict):
                                        try:
                                            await ws.send_json({
                                                "event": "simulation_tick",
                                                "data": state,
                                                "timestamp": int(time.time() * 1000),
                                            })
                                        except Exception:
                                            pass
                                    return send_tick
                                register_tick_callback(flight_id, await make_tick_sender())

                                # Register alert callback (edge computer alerts)
                                async def make_alert_sender(ws=websocket):
                                    async def send_alert(alert_data: dict):
                                        try:
                                            await ws.send_json({
                                                "event": "edge_alert",
                                                "data": alert_data,
                                                "timestamp": int(time.time() * 1000),
                                            })
                                        except Exception:
                                            pass
                                    return send_alert
                                register_alert_callback(flight_id, await make_alert_sender())

                                # Register edge telemetry callback
                                async def make_telemetry_sender(ws=websocket):
                                    async def send_telemetry(telem_data: dict):
                                        try:
                                            await ws.send_json({
                                                "event": "edge_telemetry",
                                                "data": telem_data,
                                                "timestamp": int(time.time() * 1000),
                                            })
                                        except Exception:
                                            pass
                                    return send_telemetry
                                register_edge_telemetry_callback(flight_id, await make_telemetry_sender())

                        if tool_name in (
                            "start_simulation", "step_simulation",
                            "generate_correction", "complete_flight",
                            "create_corridor",
                        ):
                            await websocket.send_json({
                                "event": "simulation_updated",
                                "data": {"tool": tool_name},
                                "timestamp": int(time.time() * 1000),
                            })

            elif action == "ping":
                await websocket.send_json({
                    "event": "pong",
                    "timestamp": int(time.time() * 1000),
                })

    except WebSocketDisconnect:
        logger.info("[Corridor Agent WS] Client disconnected")
    except Exception as e:
        logger.exception(f"[Corridor Agent WS] Error: {e}")
        try:
            await websocket.send_json({
                "event": "error",
                "data": {"message": str(e)},
                "timestamp": int(time.time() * 1000),
            })
        except Exception:
            pass


# ============================================================================
# SSE Streaming Endpoint
# ============================================================================

@router.post("/execute/stream")
async def execute_stream(request: ExecuteRequest):
    """SSE streaming endpoint for agent execution."""
    agent = CorridorAgent(
        job_id=request.job_id,
        max_iterations=request.max_iterations or 40,
    )

    async def event_generator():
        async for event in agent.run(request.message):
            frontend_event = map_event_to_frontend(event, request.job_id)
            yield f"data: {json.dumps(frontend_event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# Synchronous Endpoint
# ============================================================================

@router.post("/execute", response_model=ExecuteResponse)
async def execute_sync(request: ExecuteRequest):
    """Synchronous endpoint - runs agent to completion."""
    agent = CorridorAgent(
        job_id=request.job_id,
        max_iterations=request.max_iterations or 40,
    )
    result = await agent.run_to_completion(request.message)
    return ExecuteResponse(
        content=result["content"],
        duration_s=result["duration_s"],
        tool_calls=result["tool_calls"],
    )


# ============================================================================
# Mission Endpoint
# ============================================================================

@router.post("/mission")
async def run_mission(request: MissionRequest):
    """Execute a full corridor mission: design -> fly -> certify."""
    mission_prompt = (
        f"Execute a complete drone corridor mission:\n"
        f"1. Create corridor '{request.corridor_name}' from "
        f"({request.start_lat}, {request.start_lon}) to ({request.end_lat}, {request.end_lon}) "
        f"at H3 resolution {request.resolution}\n"
        f"2. Validate the corridor\n"
        f"3. Start a simulation on the corridor\n"
        f"4. Monitor the flight for {request.monitor_cycles} cycles "
        f"(check block membership, step simulation each cycle)\n"
        f"5. Complete the flight\n"
        f"6. Verify chain integrity and generate a compliance certificate"
    )

    agent = CorridorAgent(job_id=request.job_id, max_iterations=40)

    async def event_generator():
        async for event in agent.run(mission_prompt):
            frontend_event = map_event_to_frontend(event, request.job_id)
            yield f"data: {json.dumps(frontend_event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# Info Endpoints
# ============================================================================

@router.get("/tools")
async def list_tools():
    """List all available agent tools."""
    from .tools.registry import get_tool_definitions
    return {"tools": get_tool_definitions(), "count": len(get_tool_definitions())}


@router.get("/agents")
async def list_agents():
    """List available agent configurations."""
    from pathlib import Path
    configs_dir = Path(__file__).parent.parent.parent / "configs" / "agents"
    agents = []
    if configs_dir.exists():
        for f in sorted(configs_dir.glob("*.yaml")):
            agents.append({"name": f.stem, "path": str(f.relative_to(configs_dir.parent.parent))})
    return {"agents": agents}
