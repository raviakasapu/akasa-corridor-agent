# FastAPI Multi-Agent Architecture Strategy

This document describes the current FastAPI agent stack in [`app/main.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/main.py), the YAML-driven agent configuration model in [`configs/agents/`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents), and the next implementation steps needed to complete the multi-agent backend.

## 1. Architecture Overview

The backend supports two execution styles behind one FastAPI surface:

- Single-agent mode: one `CorridorAgent` instance owns all 18 tools and handles the full task end to end.
- Multi-agent mode: an orchestrator routes work to specialist workers for corridor design, flight monitoring, and compliance.
- YAML-based configuration: agent topology, prompts, models, memory, and worker routing are encoded in YAML so runtime behavior can be changed without rewriting the API layer.

### Single-agent mode

The default API path uses [`CorridorAgent`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/agent.py) in `mode="single"`. In that branch, `_create_single_agent()` builds one `SingleAgent` with:

- one Bedrock gateway
- one `ThreeTierMemory` session keyed by `job_id`
- all tool definitions returned by `build_tool_definitions()`
- one shared tool executor from `create_tool_executor()`

This is the simplest operating mode for synchronous REST, SSE streaming, and WebSocket execution because the API only needs one wrapper object.

```python
agent = CorridorAgent(
    job_id="mission-001",
    mode="single",
    max_iterations=20,
)
```

Flow:

```text
Client request
  -> FastAPI endpoint
  -> CorridorAgent(mode="single")
  -> SingleAgent with all 18 tools
  -> tool registry / executor
  -> streamed or final response
```

### Multi-agent mode

The multi-agent design is encoded in [`configs/agents/orchestrator.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/orchestrator.yaml). The orchestrator is a `ManagerAgent` that:

- plans which worker should handle the task
- routes phases to one of three specialists
- stores shared mission state in orchestrator memory
- synthesizes worker outputs into a final JSON response

Worker split:

- `corridor_designer`: create and validate corridors
- `flight_guardian`: run simulation, detect deviations, correct flight path
- `compliance_recorder`: verify ledger integrity and issue certificates

Flow:

```text
Client request
  -> FastAPI endpoint
  -> CorridorAgent.from_config(... orchestrator.yaml)
  -> ManagerAgent planner
  -> designer / guardian / compliance worker
  -> synthesizer
  -> final structured response
```

### YAML-based configuration pattern

YAML is the contract between infrastructure and runtime. The code in [`app/sdk_agent/agent.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/agent.py) supports both:

- programmatic creation via constructors such as `create_guardian_agent()`
- configuration-based creation via `CorridorAgent.from_config()`

That split is useful because:

- local development can start with direct Python construction
- deployment can switch models, prompts, and workers via YAML
- new agents can be introduced without changing FastAPI route definitions

## 2. File Structure Created

### `app/`

- [`app/main.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/main.py): FastAPI app bootstrap, CORS, `/health`, root metadata, router wiring, and `/ws/agent`.
- [`app/core/config.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/core/config.py): environment-backed application settings.
- [`app/core/logging.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/core/logging.py): logging setup for the backend process.
- [`app/sdk_agent/agent.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/agent.py): `CorridorAgent` wrapper, programmatic factories, config loading, tool definition bridging.
- [`app/sdk_agent/api.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/api.py): REST, SSE, and WebSocket-facing agent execution helpers and request models.
- [`app/sdk_agent/tools/registry.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/tools/registry.py): global tool registry, `@tool` decorator, `execute_tool()`, and tool metadata export.
- [`app/sdk_agent/tools/corridor/management.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/tools/corridor/management.py): corridor-management tools.
- [`app/sdk_agent/tools/simulation/drone_tools.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/tools/simulation/drone_tools.py): drone simulation tool entrypoints.
- [`app/sdk_agent/tools/simulation/engine.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/tools/simulation/engine.py): simulation engine state and flight progression logic.
- [`app/sdk_agent/tools/compliance/ledger_tools.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/tools/compliance/ledger_tools.py): compliance and certificate tools.
- [`app/sdk_agent/orchestrator/orchestrator.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/orchestrator/orchestrator.py): orchestration runtime using `CorridorAgent` workers.
- [`app/sdk_agent/orchestrator/templates.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/orchestrator/templates.py): reusable mission template definitions.
- [`app/sdk_agent/memory/job_memory.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/memory/job_memory.py): job-scoped mission state tracking across phases.
- [`app/__init__.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/__init__.py), [`app/core/__init__.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/core/__init__.py), [`app/sdk_agent/__init__.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/__init__.py), [`app/sdk_agent/memory/__init__.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/memory/__init__.py), [`app/sdk_agent/orchestrator/__init__.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/orchestrator/__init__.py), [`app/sdk_agent/tools/corridor/__init__.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/tools/corridor/__init__.py), [`app/sdk_agent/tools/simulation/__init__.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/tools/simulation/__init__.py), [`app/sdk_agent/tools/compliance/__init__.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/tools/compliance/__init__.py): package markers and import surfaces.

### `configs/`

- [`configs/agents/sdk_agent.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/sdk_agent.yaml): standalone `SingleAgent` with all 18 tools.
- [`configs/agents/orchestrator.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/orchestrator.yaml): `ManagerAgent` planner, synthesizer, shared memory, and worker map.
- [`configs/agents/corridor_designer.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/corridor_designer.yaml): worker config for corridor creation and validation.
- [`configs/agents/flight_guardian.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/flight_guardian.yaml): worker config for simulation and correction loops.
- [`configs/agents/compliance_recorder.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/compliance_recorder.yaml): worker config for audit and certificate generation.

## 3. Agent Modes

### `SingleAgent` via `sdk_agent.yaml`

[`configs/agents/sdk_agent.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/sdk_agent.yaml) defines one standalone agent with all 18 tools across:

- 4 corridor tools
- 10 simulation tools
- 4 compliance tools

This is the lowest-friction runtime for:

- `/api/v1/execute`
- `/api/v1/execute/stream`
- `/ws/agent`

Representative snippet:

```yaml
apiVersion: agent.framework/v1
kind: SingleAgent
metadata:
  name: Akasa_Corridor_Agent
gateway:
  type: ${LLM_GATEWAY:-BedrockGateway}
agent:
  max_iterations: 25
tools:
  - name: create_corridor
  - name: start_simulation
  - name: generate_certificate
memory:
  type: ThreeTierMemory
  session_id: ${JOB_ID}
```

### `ManagerAgent` via `orchestrator.yaml`

[`configs/agents/orchestrator.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/orchestrator.yaml) defines the coordinator runtime. Its planner chooses a worker, and its synthesizer normalizes outputs into a final JSON payload.

Representative snippet:

```yaml
apiVersion: agent.framework/v2
kind: ManagerAgent
resources:
  inference_gateways:
    - name: orchestrator-gateway
spec:
  workers:
    - name: designer
      config_path: corridor_designer.yaml
    - name: guardian
      config_path: flight_guardian.yaml
    - name: compliance
      config_path: compliance_recorder.yaml
```

### Worker agents

[`configs/agents/corridor_designer.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/corridor_designer.yaml)

- Purpose: create corridor geometry and validate it before flight.
- Tool scope: `create_corridor`, `list_corridors`, `get_corridor_detail`, `validate_corridor`.

[`configs/agents/flight_guardian.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/flight_guardian.yaml)

- Purpose: operate the monitoring loop and apply corrections.
- Tool scope: simulation lifecycle, position checks, disturbance injection, telemetry, emergency actions.

[`configs/agents/compliance_recorder.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/compliance_recorder.yaml)

- Purpose: audit the completed mission and produce a compliance artifact.
- Tool scope: event retrieval, chain verification, scoring, certificate generation.

## 4. YAML Configuration Pattern

### SingleAgent structure

Current single-agent YAMLs follow this shape:

```yaml
apiVersion: agent.framework/v1
kind: SingleAgent

metadata:
  name: <agent-name>
  version: <semver>
  description: <what this agent does>

gateway:
  type: <gateway-class>
  config:
    model: <foundation-model>
    region: <aws-region>
    max_tokens: <int>
    temperature: <float>

agent:
  system_prompt: |
    <role and operating rules>
  max_iterations: <int>

tools:
  - name: <tool-name>
    category: <read|write>
    description: <tool purpose>

memory:
  type: ThreeTierMemory
  max_messages: <int>
  session_id: ${JOB_ID}
```

This pattern is used by:

- [`configs/agents/sdk_agent.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/sdk_agent.yaml)
- [`configs/agents/corridor_designer.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/corridor_designer.yaml)
- [`configs/agents/flight_guardian.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/flight_guardian.yaml)
- [`configs/agents/compliance_recorder.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/compliance_recorder.yaml)

### ManagerAgent structure

The orchestrator YAML follows a different shape because it needs shared resources and worker routing:

```yaml
apiVersion: agent.framework/v2
kind: ManagerAgent

metadata:
  name: <manager-name>
  description: <routing role>
  version: <semver>

resources:
  inference_gateways:
    - name: <gateway-name>
      type: <gateway-class>
      config:
        model: <planner-model>
  subscribers:
    - name: logging
      type: LoggingSubscriber

spec:
  policies:
    $preset: manager_with_followups
  workers:
    - name: <worker-key>
      config_path: <worker-yaml>
  memory:
    type: SharedInMemoryMemory
    config:
      namespace: ${JOB_ID:-default}
      agent_key: orchestrator
  planner:
    type: StrategicPlanner
    config:
      inference_gateway: <gateway-name>
      worker_keys: [<worker-key>]
      planning_prompt: |
        <routing rubric>
  synthesizer:
    enabled: true
    inference_gateway: <gateway-name>
    system_prompt: |
      <output contract>
```

### How to add a new agent

1. Create a new YAML file under [`configs/agents/`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents).
2. Limit the tool list and prompt to a single responsibility.
3. If the agent will be used programmatically, add a factory in [`app/sdk_agent/agent.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/agent.py).
4. If it should participate in orchestration, register it in [`configs/agents/orchestrator.yaml`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/configs/agents/orchestrator.yaml) under `spec.workers` and add it to the planner prompt and `worker_keys`.
5. If it requires new capabilities, register new tools in [`app/sdk_agent/tools/registry.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/tools/registry.py) and their implementation modules.

Minimal worker example:

```yaml
apiVersion: agent.framework/v1
kind: SingleAgent
metadata:
  name: Incident_Responder
  version: 1.0.0
  description: Handles incident triage
gateway:
  type: ${LLM_GATEWAY:-BedrockGateway}
  config:
    model: ${WORKER_MODEL}
agent:
  system_prompt: |
    You handle mission incidents only.
  max_iterations: 8
tools:
  - name: emergency_land
    category: write
    description: Abort flight
memory:
  type: ThreeTierMemory
  max_messages: 20
  session_id: ${JOB_ID}
```

## 5. API Endpoints

### `/health`

Defined in [`app/main.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/main.py). Returns service status, version, and whether `agent_framework` loaded successfully.

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "agent_framework": AGENT_FRAMEWORK_VERSION if SDK_AGENT_AVAILABLE else None,
    }
```

### `/api/v1/execute`

Defined in [`app/sdk_agent/api.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/api.py). Runs the agent to completion and returns a synchronous JSON response.

```python
@router.post("/execute", response_model=ExecuteResponse)
async def execute_sync(request: ExecuteRequest):
    agent = CorridorAgent(
        job_id=request.job_id,
        max_iterations=request.max_iterations or 20,
    )
    result = await agent.run_to_completion(request.message)
    return ExecuteResponse(
        content=result["content"],
        duration_s=result["duration_s"],
        tool_calls=result["tool_calls"],
    )
```

### `/api/v1/execute/stream`

Defined in [`app/sdk_agent/api.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/api.py). Streams execution events as Server-Sent Events.

```python
@router.post("/execute/stream")
async def execute_stream(request: ExecuteRequest):
    agent = CorridorAgent(job_id=request.job_id)

    async def event_generator():
        async for event in agent.run(request.message):
            frontend_event = map_event_to_frontend(event, request.job_id)
            yield f"data: {json.dumps(frontend_event)}\n\n"
```

### `/ws/agent`

Mounted in [`app/main.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/main.py) and implemented by `websocket_agent()` in [`app/sdk_agent/api.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/api.py). Supports:

- `set_context`
- `execute`
- `ping`

Representative message flow:

```json
{"action":"set_context","job_id":"mission-001","mode":"single"}
{"action":"execute","job_id":"mission-001","message":"Create and validate a corridor"}
```

## 6. Usage Examples

### Programmatic

Use direct construction when the app controls execution mode explicitly:

```python
from app.sdk_agent.agent import CorridorAgent

agent = CorridorAgent(job_id="mission-001", mode="single")
result = await agent.run_to_completion("Create a corridor from SF to Oakland")
```

### Config-based

Use YAML when the runtime should load topology and prompts from config:

```python
from app.sdk_agent.agent import CorridorAgent

agent = CorridorAgent.from_config(
    job_id="mission-001",
    config_path="configs/agents/orchestrator.yaml",
)
```

`from_config()` in [`app/sdk_agent/agent.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/agent.py) loads the YAML through `ConfigLoader`, sets `JOB_ID`, builds tool definitions, and constructs the framework agent via `SingleAgent.from_config(...)`.

### API calls with `curl`

Sync request:

```bash
curl -X POST http://localhost:8052/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "mission-001",
    "message": "Create and validate a corridor from San Francisco to Oakland",
    "max_iterations": 20
  }'
```

SSE request:

```bash
curl -N -X POST http://localhost:8052/api/v1/execute/stream \
  -H "Content-Type: application/json" \
  -d '{
    "job_id": "mission-001",
    "message": "Run a full mission and stream each step"
  }'
```

Health check:

```bash
curl http://localhost:8052/health
```

### API calls with Python

Sync:

```python
import requests

response = requests.post(
    "http://localhost:8052/api/v1/execute",
    json={
        "job_id": "mission-001",
        "message": "Create and validate a corridor",
        "max_iterations": 20,
    },
    timeout=120,
)
print(response.json())
```

Streaming:

```python
import requests

with requests.post(
    "http://localhost:8052/api/v1/execute/stream",
    json={
        "job_id": "mission-001",
        "message": "Monitor the flight and stream tool calls",
    },
    stream=True,
    timeout=120,
) as response:
    for line in response.iter_lines():
        if line:
            print(line.decode())
```

## 7. Next Steps

### 1. Implement tool executor integration

The basic bridge already exists in [`app/sdk_agent/agent.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/agent.py) and [`app/sdk_agent/tools/registry.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/tools/registry.py), but the next step is to formalize:

- typed tool result envelopes
- consistent error contracts
- async-safe execution for long-running tools
- better observability around tool latency and failures

### 2. Add memory persistence

The current configs use in-memory session state. Persisting mission memory should move:

- agent conversation history
- mission phase outputs
- compliance artifacts
- resumable job metadata

Likely integration points:

- [`app/sdk_agent/memory/job_memory.py`](/Users/autoai-mini/Documents/axplusb/akasa-corridor-agent/app/sdk_agent/memory/job_memory.py)
- `ThreeTierMemory` / shared-memory config substitution

### 3. Deploy to Railway

Deployment work should package:

- FastAPI process startup
- env var configuration for Bedrock and model selection
- persistent backing services if memory is externalized
- health checks on `/health`

Minimal run target:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 4. Create frontend dashboard

The API surface already supports a dashboard with:

- WebSocket event streaming from `/ws/agent`
- SSE fallback via `/api/v1/execute/stream`
- agent capability discovery via `/api/v1/tools` and `/api/v1/agents`

The frontend should expose:

- job creation and selection
- real-time event timeline
- tool-call trace view
- mission summary and certificate display

## Recommended Implementation Sequence

1. Finish config-driven multi-agent loading on the main execution path so `orchestrator.yaml` can be used by the API directly.
2. Harden tool execution contracts and telemetry.
3. Persist job memory and mission outputs.
4. Deploy the backend to Railway.
5. Build the dashboard against WebSocket and SSE endpoints.
