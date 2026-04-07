# Akasa Corridor Agent — Multi-Agent Architecture

## Overview

FastAPI backend with YAML-driven multi-agent orchestration for autonomous drone corridor management. Adapted from the power-bi-backend-agent-v2 patterns, using the same `auto-ai-agent-framework` composable module.

## Architecture

```
┌──────────────────────────────────────────────────┐
│  FastAPI (app/main.py)                           │
│  ├── /health                                     │
│  ├── /ws/agent          (WebSocket streaming)    │
│  ├── /api/v1/execute    (sync REST)              │
│  ├── /api/v1/execute/stream  (SSE streaming)     │
│  ├── /api/v1/mission    (full mission SSE)       │
│  ├── /api/v1/tools      (list tools)             │
│  └── /api/v1/agents     (list agent configs)     │
└──────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────┐
│  CorridorAgent (app/sdk_agent/agent.py)          │
│  ├── mode="single"   → all 18 tools             │
│  ├── mode="guardian"  → flight monitoring tools  │
│  ├── mode="designer"  → corridor tools           │
│  ├── mode="compliance"→ compliance tools         │
│  └── mode="config"    → from YAML file           │
└──────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────┐
│  MissionOrchestrator                             │
│  (app/sdk_agent/orchestrator/orchestrator.py)    │
│                                                  │
│  Templates: full_mission, corridor_only,         │
│             compliance_audit                     │
│                                                  │
│  Flow: designer → guardian → compliance          │
│  Context: previous task results passed forward   │
└──────────────────────────────────────────────────┘
```

## Two Operating Modes

### 1. Single-Agent Mode (standalone)

One agent with all 18 tools handles any request. Used by `/api/v1/execute` and `/ws/agent`.

**Config:** `configs/agents/sdk_agent.yaml`

```
User → CorridorAgent(mode="single") → all tools
```

### 2. Multi-Agent Mode (orchestrated)

MissionOrchestrator runs templates with specialized agents per phase.

**Config:** `configs/agents/orchestrator.yaml` + worker YAML files

```
User → MissionOrchestrator
       ├── Phase 1: CorridorAgent(mode="designer")  → corridor tools
       ├── Phase 2: CorridorAgent(mode="guardian")   → simulation tools
       └── Phase 3: CorridorAgent(mode="compliance") → compliance tools
```

## YAML Configuration Pattern

### SingleAgent (worker)

```yaml
apiVersion: agent.framework/v1
kind: SingleAgent
metadata: { name, version, description }
gateway: { type, config: { model, region, max_tokens, temperature } }
agent: { system_prompt, max_iterations }
tools: [ { name, category, description } ]
memory: { type, max_messages, session_id }
```

### ManagerAgent (orchestrator)

```yaml
apiVersion: agent.framework/v2
kind: ManagerAgent
metadata: { name, version, description }
resources: { inference_gateways, subscribers }
spec:
  planner: { type, config: { planning_prompt, worker_keys } }
  synthesizer: { system_prompt }
  workers: [ { name, config_path } ]
  memory: { type, config: { namespace, agent_key } }
```

## Multi-LLM Strategy (AWS Bedrock)

| Role | Model | Rationale |
|------|-------|-----------|
| Coordinator / Guardian | Claude Haiku 4.5 | Safety-critical reasoning |
| Designer / Compliance | Qwen 3 VL 235B | Tool calling, cost-effective |

Configured via env vars: `COORDINATOR_MODEL`, `GUARDIAN_MODEL`, `WORKER_MODEL`

## File Structure

```
akasa-corridor-agent/
├── app/
│   ├── main.py                          # FastAPI app, CORS, routers, health
│   ├── core/
│   │   ├── config.py                    # Settings (pydantic-settings)
│   │   └── logging.py                   # Rich color-coded logging
│   ├── sdk_agent/
│   │   ├── agent.py                     # CorridorAgent + factory functions
│   │   ├── api.py                       # REST + WebSocket + SSE endpoints
│   │   ├── tools/
│   │   │   ├── registry.py              # @tool decorator + execute_tool()
│   │   │   ├── simulation/              # 10 drone simulation tools
│   │   │   ├── corridor/                # 4 corridor management tools
│   │   │   └── compliance/              # 4 compliance tools
│   │   ├── orchestrator/
│   │   │   ├── orchestrator.py          # MissionOrchestrator
│   │   │   └── templates.py             # Mission templates
│   │   └── memory/
│   │       └── job_memory.py            # Cross-task context tracking
│   └── guidance/                         # (future: domain guidance docs)
├── configs/
│   └── agents/
│       ├── sdk_agent.yaml               # SingleAgent (all tools)
│       ├── orchestrator.yaml            # ManagerAgent (routes to workers)
│       ├── corridor_designer.yaml       # Worker: corridor tools
│       ├── flight_guardian.yaml          # Worker: simulation tools
│       └── compliance_recorder.yaml     # Worker: compliance tools
├── tests/                               # Existing test suite
├── docs/
│   └── ARCHITECTURE.md                  # This document
├── pyproject.toml
└── .env.example
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ws/agent` | WS | Real-time agent streaming |
| `/api/v1/execute` | POST | Sync execution |
| `/api/v1/execute/stream` | POST | SSE streaming |
| `/api/v1/mission` | POST | Full mission (SSE) |
| `/api/v1/tools` | GET | List all tools |
| `/api/v1/agents` | GET | List agent configs |

## WebSocket Protocol

```json
// Client → Server
{"action": "set_context", "job_id": "mission-001", "mode": "single"}
{"action": "execute", "message": "Create a corridor from SF to Oakland", "job_id": "mission-001"}

// Server → Client
{"event": "connected", "data": {"agent": "akasa-corridor-agent"}}
{"event": "status", "data": {"message": "Starting..."}}
{"event": "tool_call", "data": {"tool": "create_corridor", "args": {...}}}
{"event": "tool_done", "data": {"tool": "create_corridor", "result": {...}}}
{"event": "content", "data": {"text": "Corridor created successfully..."}}
{"event": "complete", "data": {"duration_s": 12.3, "tool_calls": 4}}
{"event": "simulation_updated", "data": {"tool": "step_simulation"}}
```

## Running

```bash
# Development
uvicorn app.main:app --host localhost --port 8052 --reload

# Production
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
