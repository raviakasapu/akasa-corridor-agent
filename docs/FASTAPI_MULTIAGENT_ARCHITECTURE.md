# FastAPI Multi-Agent Architecture — Akasa Corridor Agent

> Comprehensive reference for the YAML-driven multi-agent drone corridor system.
> Adapted from [power-bi-backend-agent-v2](../README.md#related-repositories) patterns.

---

## 1. Architecture Overview

The system supports **two operating modes** through a single FastAPI backend:

```
                         ┌─────────────────────────────────┐
                         │       FastAPI Backend            │
                         │       (app/main.py)              │
                         │                                  │
                         │  /health          GET  health    │
                         │  /ws/agent        WS   stream    │
                         │  /api/v1/execute  POST  sync     │
                         │  /api/v1/execute/stream  SSE     │
                         │  /api/v1/mission  POST  mission  │
                         │  /api/v1/tools    GET   info     │
                         │  /api/v1/agents   GET   info     │
                         └────────────┬────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                                    ▼
       ┌────────────────────┐             ┌────────────────────────┐
       │  SINGLE-AGENT MODE │             │  MULTI-AGENT MODE      │
       │                    │             │                        │
       │  CorridorAgent     │             │  MissionOrchestrator   │
       │  mode="single"     │             │  (template-driven)     │
       │  all 18 tools      │             │                        │
       │                    │             │  Phase 1: Designer     │
       │  Handles any       │             │  Phase 2: Guardian     │
       │  request directly  │             │  Phase 3: Compliance   │
       └────────────────────┘             └────────────────────────┘
```

### Single-Agent Mode

One `CorridorAgent` with all 18 tools handles any request. Best for interactive use, simple tasks, and the WebSocket/REST API.

```
User message → CorridorAgent(mode="single") → all 18 tools → response
```

### Multi-Agent Mode

`MissionOrchestrator` executes predefined templates, delegating each phase to a specialist agent. Context from previous phases is automatically injected into subsequent phases.

```
Template "full_mission" →
  Phase 1: CorridorAgent(mode="designer")   → create_corridor, validate_corridor
  Phase 2: CorridorAgent(mode="guardian")    → start_simulation, check_block_membership, ...
  Phase 3: CorridorAgent(mode="compliance")  → verify_chain_integrity, generate_certificate
```

---

## 2. File Structure

### app/ — Application Code

```
app/
├── __init__.py
├── main.py                              # FastAPI app, CORS, routers, health check
│                                         # Mounts /ws/agent and /api/v1/* routes
│
├── core/
│   ├── __init__.py
│   ├── config.py                        # pydantic-settings: gateway, CORS, multi-LLM
│   │                                     # Reads from .env via Settings class
│   └── logging.py                       # Rich color-coded logging
│                                         # Agent colors: coordinator=magenta, guardian=cyan,
│                                         # designer=green, compliance=blue
│
├── sdk_agent/
│   ├── __init__.py
│   ├── agent.py                         # CorridorAgent wrapper class
│   │                                     # + factory functions: create_guardian_agent(),
│   │                                     #   create_corridor_designer_agent(),
│   │                                     #   create_compliance_agent()
│   │                                     # + system prompts for all agent roles
│   │
│   ├── api.py                           # FastAPI router at /api/v1
│   │                                     # WebSocket handler, SSE streaming, sync endpoint,
│   │                                     # mission endpoint, tools list, agents list
│   │                                     # Event mapping: AgentEvent → frontend JSON format
│   │
│   ├── tools/
│   │   ├── registry.py                  # @tool decorator + execute_tool() + get_tool_definitions()
│   │   ├── simulation/
│   │   │   ├── engine.py                # DroneSimulator, FlightLedger, H3 geocode
│   │   │   └── drone_tools.py           # 10 tools: start/step/position/block/correct/wind/gps/...
│   │   ├── corridor/
│   │   │   └── management.py            # 4 tools: create/list/detail/validate corridor
│   │   └── compliance/
│   │       └── ledger_tools.py          # 4 tools: events/chain/score/certificate
│   │
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── orchestrator.py              # MissionOrchestrator: sequential multi-agent execution
│   │   │                                 # Context passing between phases via _build_context_prefix()
│   │   └── templates.py                 # Predefined templates: full_mission, corridor_only,
│   │                                     # compliance_audit
│   │
│   └── memory/
│       ├── __init__.py
│       └── job_memory.py                # JobMemory: tracks task results, tool summaries,
│                                         # cross-task context for orchestrator
│
└── guidance/                             # (placeholder for future domain guidance docs)
```

### configs/ — YAML Agent Configurations

```
configs/
└── agents/
    ├── sdk_agent.yaml                   # SingleAgent — all 18 tools, standalone mode
    ├── orchestrator.yaml                # ManagerAgent — routes to designer/guardian/compliance
    ├── corridor_designer.yaml           # Worker: 4 corridor tools (Qwen 3 VL)
    ├── flight_guardian.yaml             # Worker: 10 simulation tools (Claude Haiku 4.5)
    └── compliance_recorder.yaml         # Worker: 5 compliance tools (Qwen 3 VL)
```

---

## 3. Agent Modes and YAML Patterns

### CorridorAgent Modes

| Mode | Model | Tools | Use Case |
|------|-------|-------|----------|
| `single` | `LLM_MODEL` | All 18 | Interactive API, general requests |
| `guardian` | `GUARDIAN_MODEL` | 10 simulation | Flight monitoring phase |
| `designer` | `WORKER_MODEL` | 4 corridor | Corridor creation phase |
| `compliance` | `WORKER_MODEL` | 5 compliance | Certification phase |
| `config` | from YAML | from YAML | Config-driven creation |

### YAML Pattern: SingleAgent (Worker)

Used for standalone agents and orchestrator workers.

```yaml
apiVersion: agent.framework/v1
kind: SingleAgent

metadata:
  name: Agent_Name
  version: 1.0.0
  description: What this agent does

gateway:
  type: ${LLM_GATEWAY:-BedrockGateway}      # Env var with default
  config:
    model: ${WORKER_MODEL:-qwen.qwen3-vl-235b-a22b}
    region: ${AWS_REGION:-us-east-1}
    max_tokens: 1024
    temperature: 0.1
    cache:
      enabled: true
      cache_system_prompt: true
      cache_tools: true

agent:
  system_prompt: |
    Role description and instructions...
  max_iterations: 10

tools:
  - name: tool_name
    category: read|write
    description: What the tool does

memory:
  type: ThreeTierMemory
  max_messages: 30
  session_id: ${JOB_ID}
```

### YAML Pattern: ManagerAgent (Orchestrator)

Used for the top-level mission coordinator that routes to workers.

```yaml
apiVersion: agent.framework/v2
kind: ManagerAgent

metadata:
  name: Orchestrator_Name
  version: 1.0.0
  description: Routes tasks to specialist workers

resources:
  inference_gateways:
    - name: orchestrator-gateway
      type: ${LLM_GATEWAY:-BedrockGateway}
      config:
        model: ${COORDINATOR_MODEL:-global.anthropic.claude-haiku-4-5-20251001-v1:0}
        region: ${AWS_REGION:-us-east-1}
        temperature: 0.1

  subscribers:
    - name: logging
      type: LoggingSubscriber
      config:
        level: INFO

spec:
  workers:
    - name: designer
      config_path: corridor_designer.yaml
    - name: guardian
      config_path: flight_guardian.yaml
    - name: compliance
      config_path: compliance_recorder.yaml

  planner:
    type: StrategicPlanner
    config:
      inference_gateway: orchestrator-gateway
      worker_keys: [designer, guardian, compliance]
      planning_prompt: |
        Route user intent to the appropriate worker...

  synthesizer:
    enabled: true
    inference_gateway: orchestrator-gateway
    system_prompt: |
      Format worker results into structured JSON...

  memory:
    type: SharedInMemoryMemory
    config:
      namespace: ${JOB_ID:-default}
      agent_key: orchestrator
```

### Multi-LLM Strategy

| Role | Model | Env Var | Rationale |
|------|-------|---------|-----------|
| Coordinator | Claude Haiku 4.5 | `COORDINATOR_MODEL` | Safety-critical routing decisions |
| Guardian | Claude Haiku 4.5 | `GUARDIAN_MODEL` | Safety-critical flight monitoring |
| Designer | Qwen 3 VL 235B | `WORKER_MODEL` | Tool calling, cost-effective (~3x cheaper) |
| Compliance | Qwen 3 VL 235B | `WORKER_MODEL` | Tool calling, cost-effective |

---

## 4. API Endpoints

### REST Endpoints

| Endpoint | Method | Request Body | Description |
|----------|--------|-------------|-------------|
| `/health` | GET | — | Health check with framework version |
| `/` | GET | — | Root info with available endpoints |
| `/api/v1/execute` | POST | `ExecuteRequest` | Synchronous agent execution |
| `/api/v1/execute/stream` | POST | `ExecuteRequest` | SSE streaming execution |
| `/api/v1/mission` | POST | `MissionRequest` | Full mission SSE (design→fly→certify) |
| `/api/v1/tools` | GET | — | List all 18 registered tools |
| `/api/v1/agents` | GET | — | List available YAML agent configs |

### Request Models

```python
# ExecuteRequest — for /execute and /execute/stream
{
    "job_id": "mission-001",
    "message": "Create a corridor from SF to Oakland",
    "model": null,           # optional override
    "max_iterations": 20     # optional
}

# MissionRequest — for /mission
{
    "job_id": "mission-001",
    "start_lat": 37.7749,
    "start_lon": -122.4194,
    "end_lat": 37.8044,
    "end_lon": -122.2712,
    "corridor_name": "SF-Oakland Corridor",
    "resolution": 10,
    "monitor_cycles": 8
}
```

### WebSocket Protocol (`/ws/agent`)

```jsonc
// ── Client → Server ──

// Set context (optional, creates agent with mode)
{"action": "set_context", "job_id": "mission-001", "mode": "single"}

// Execute a task
{"action": "execute", "message": "Create a corridor", "job_id": "mission-001"}

// Keepalive
{"action": "ping"}

// ── Server → Client ──

// Connection established
{"event": "connected", "data": {"agent": "akasa-corridor-agent", "version": "1.0.0"}}

// Agent lifecycle events
{"event": "status",    "data": {"message": "Starting...", "display": "inline"}}
{"event": "thinking",  "data": {"message": "Processing...", "iteration": 1}}
{"event": "tool_call", "data": {"tool": "create_corridor", "args": {...}, "tool_index": 1}}
{"event": "tool_done", "data": {"tool": "create_corridor", "success": true, "result": {...}}}
{"event": "content",   "data": {"text": "Corridor created successfully...", "content": "..."}}
{"event": "complete",  "data": {"duration_s": 12.3, "iterations": 5, "tool_calls": 4}}

// Simulation-specific event (emitted after simulation-modifying tools)
{"event": "simulation_updated", "data": {"tool": "step_simulation"}}

// Error
{"event": "error", "data": {"message": "Tool execution failed: ..."}}
```

---

## 5. Usage Examples

### Programmatic: Single-Agent

```python
from app.sdk_agent.agent import CorridorAgent

# Create agent with all tools
agent = CorridorAgent(job_id="demo-001", mode="single")

# Run with streaming events
async for event in agent.run("Create a corridor from SF to Oakland at resolution 10"):
    print(event.type, event.data)

# Or run to completion
result = await agent.run_to_completion("List all corridors")
print(result["content"])
```

### Programmatic: Specialist Agent

```python
from app.sdk_agent.agent import CorridorAgent

# Create guardian-only agent
guardian = CorridorAgent(job_id="flight-001", mode="guardian")

# Monitor a flight
async for event in guardian.run("Monitor flight for 8 cycles"):
    print(event.type, event.data)
```

### Programmatic: Multi-Agent Orchestrator

```python
from app.sdk_agent.orchestrator import MissionOrchestrator

orch = MissionOrchestrator(job_id="mission-001")

async for event in orch.run("full_mission"):
    if event.type == "task_start":
        print(f"Phase: {event.data['task_name']} ({event.data['agent_mode']})")
    elif event.type == "task_complete":
        print(f"  Done: {event.data['tool_calls']} tool calls")
    elif event.type == "job_complete":
        print(f"Mission complete: {event.data['completed_tasks']}/{event.data['total_tasks']}")
```

### Config-Based: From YAML

```python
from app.sdk_agent.agent import CorridorAgent

# Load from default sdk_agent.yaml
agent = CorridorAgent.from_config(job_id="yaml-001")

# Load from custom config
agent = CorridorAgent.from_config(
    job_id="yaml-002",
    config_path="configs/agents/flight_guardian.yaml",
)
```

### Factory Functions (Original API — still supported)

```python
from app.sdk_agent.agent import (
    create_guardian_agent,
    create_corridor_designer_agent,
    create_compliance_agent,
)

# Direct framework SingleAgent instances
guardian = create_guardian_agent(max_iterations=20)
designer = create_corridor_designer_agent()
compliance = create_compliance_agent()

# Use with framework API
async for event in guardian.run("Monitor the corridor for 10 cycles"):
    print(event)
```

### cURL: REST API

```bash
# Health check
curl http://localhost:8052/health

# Sync execution
curl -X POST http://localhost:8052/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"job_id": "test-001", "message": "List all corridors"}'

# SSE streaming
curl -X POST http://localhost:8052/api/v1/execute/stream \
  -H "Content-Type: application/json" \
  -d '{"job_id": "test-002", "message": "Create a corridor from (37.77, -122.42) to (37.80, -122.27)"}'

# Full mission
curl -X POST http://localhost:8052/api/v1/mission \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "mission-001",
    "start_lat": 37.7749, "start_lon": -122.4194,
    "end_lat": 37.8044, "end_lon": -122.2712,
    "corridor_name": "SF-Oakland",
    "resolution": 10,
    "monitor_cycles": 8
  }'

# List tools
curl http://localhost:8052/api/v1/tools

# List agent configs
curl http://localhost:8052/api/v1/agents
```

### Running the Server

```bash
# Development (with auto-reload)
uvicorn app.main:app --host localhost --port 8052 --reload

# Production
uvicorn app.main:app --host 0.0.0.0 --port $PORT

# With explicit env
LLM_GATEWAY=BedrockGateway GUARDIAN_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0 \
  uvicorn app.main:app --port 8052
```

---

## 6. Tool Registry Pattern

All 18 tools are registered via the `@tool` decorator in `app/sdk_agent/tools/registry.py`:

```python
from app.sdk_agent.tools.registry import tool

@tool(
    name="check_block_membership",
    description="Check if drone is in assigned geocode block",
    parameters={
        "type": "object",
        "properties": {
            "flight_id": {"type": "string", "description": "Flight ID"},
        },
        "required": ["flight_id"],
    },
)
def check_block_membership(flight_id: str) -> dict:
    # Implementation...
    return {"status": "NOMINAL", "assigned_block": "8a...", "current_block": "8a..."}
```

Tools by domain:

| Domain | Count | Tools |
|--------|-------|-------|
| **Simulation** | 10 | start_simulation, step_simulation, get_drone_position, check_block_membership, generate_correction, inject_wind_gust, inject_gps_noise, get_flight_telemetry, complete_flight, emergency_land |
| **Corridor** | 4 | create_corridor, list_corridors, get_corridor_detail, validate_corridor |
| **Compliance** | 4 | get_flight_events, verify_chain_integrity, calculate_conformance_score, generate_certificate |

---

## 7. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| `CorridorAgent` wrapper class | Mirrors `PowerBIAgent` from power-bi-backend-agent-v2 — single entry point for all modes |
| YAML configs with `${ENV_VAR:-default}` | Same pattern as power-bi — deploy-time configuration without code changes |
| `BedrockGateway` default | Project uses AWS Bedrock for both Claude and Qwen models |
| Claude Haiku for safety-critical roles | Guardian/Coordinator need reliable reasoning; Claude models can't be fine-tuned |
| Qwen 3 VL for workers | Good tool calling at ~3x lower cost; suitable for deterministic tasks |
| SSE + WebSocket + REST | Three transport options match power-bi patterns; frontend can choose |
| `simulation_updated` WS event | Enables real-time UI updates for drone position visualization |
| `JobMemory` for cross-task context | Orchestrator passes summarized results between phases efficiently |
| Template-based orchestration | Predefined workflows (full_mission, corridor_only, compliance_audit) |

---

## 8. Environment Variables

```bash
# Core
LLM_GATEWAY=BedrockGateway           # Gateway type
LLM_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0  # Default model
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Multi-LLM
COORDINATOR_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0
GUARDIAN_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0
MANAGER_MODEL=global.anthropic.claude-haiku-4-5-20251001-v1:0
WORKER_MODEL=qwen.qwen3-vl-235b-a22b

# App
APP_HOST=localhost
APP_PORT=8052
DEBUG=true
ENVIRONMENT=development

# Features
ENABLE_PROMPT_CACHING=true
WS_ENABLED=true
WS_TOKEN=your-ws-token
```

---

## 9. Comparison with power-bi-backend-agent-v2

| Aspect | power-bi-backend-agent-v2 | akasa-corridor-agent |
|--------|--------------------------|---------------------|
| Wrapper class | `PowerBIAgent` | `CorridorAgent` |
| API prefix | `/api/v4` | `/api/v1` |
| Agent modes | single, config | single, guardian, designer, compliance, config |
| Orchestrator | `Orchestrator` + `PowerBIOrchestrator` | `MissionOrchestrator` |
| YAML configs | 6 workers + orchestrator | 3 workers + orchestrator + standalone |
| Gateway | OpenRouter / Claude / Bedrock | Bedrock only |
| Tool count | 50+ (data model, report, publish) | 18 (simulation, corridor, compliance) |
| Memory | `EnhancedJobMemory` | `JobMemory` |
| Domain events | `model_updated` | `simulation_updated` |
| Templates | validate_and_fix_dax, etc. | full_mission, corridor_only, compliance_audit |

---

## 10. Next Steps

### Immediate

- [ ] **Test API endpoints** — start server, verify `/health`, test WebSocket with a client
- [ ] **Wire orchestrator to API** — add `/api/v1/orchestrate` endpoint that runs templates
- [ ] **Add `pydantic-settings`** dependency resolution — ensure `pip install -e .` works cleanly

### Short-term

- [ ] **Frontend web interface** — React/Vite dashboard with:
  - Map visualization (H3 hexagon cells, corridor path, drone position)
  - Real-time WebSocket connection for live flight monitoring
  - Mission control panel (create corridor, start mission, view certificate)
- [ ] **Guidance system** — populate `app/guidance/` with domain docs for corridor design patterns
- [ ] **Deploy to Railway** — add `railway.json`, `Dockerfile`, health check at `/health`
- [ ] **Add Vercel frontend** — React app connecting to Railway backend via WebSocket

### Medium-term

- [ ] **Config-driven orchestrator** — load `orchestrator.yaml` via `ManagerAgent.from_config()` for full YAML-driven multi-agent routing (currently uses programmatic `MissionOrchestrator`)
- [ ] **Tool filtering** — semantic tool retrieval (like power-bi's `ToolRetriever`) to reduce token usage
- [ ] **Shared memory between agents** — use `SharedInMemoryMemory` for corridor_id/flight_id passing
- [ ] **Event replay** — record and replay mission events for debugging
- [ ] **Multi-corridor support** — concurrent flights on different corridors
