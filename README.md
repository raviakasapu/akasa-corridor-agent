# Ākāsā Corridor Agent

> Autonomous drone corridor management system built on the [Auto AI Agent Framework](https://github.com/raviakasapu/auto-ai-agent-framework) — validates both the Ākāsā patent concepts and the framework's multi-agent capabilities.

## What This Does

A multi-agent system that designs, monitors, and certifies autonomous drone flights along geocode-addressed corridors. Real LLM reasoning (Claude Haiku + Qwen 3 on AWS Bedrock), simulated drone physics, real H3 geocode resolution, and real SHA-256 cryptographic compliance ledger.

### The Patent Concepts Proven

| Concept | Implementation |
|---|---|
| **Geocode-addressed corridors** | H3 hexagonal cells form ordered "digital rails" |
| **Onboard control loop** | Satellite position → H3 cell → compare to assigned block → correct |
| **Crypto-chained flight ledger** | SHA-256 append-only hash chain, tamper-detectable |
| **Compliance Certificate** | Per-flight certificate with conformance score and chain hash |
| **Multi-agent coordination** | Coordinator → Designer + Guardian + Compliance specialists |

### The Framework Features Exercised

| Feature | Status |
|---|---|
| SingleAgent tool-use loop | Tested |
| Multi-agent SequentialPattern | Tested |
| AgentProfile + SpecialistAgent | Tested |
| CoordinatorAgent | Tested |
| SharedMemory (cross-agent artifacts) | Tested |
| ThreeTierMemory with summarizer + promoter | Tested |
| ContextAssembler with token budget | Tested |
| Multi-LLM (Haiku + Qwen on Bedrock) | Tested |
| Event system (lifecycle tracking) | Tested |
| Tool executor with timeout + truncation | Available |
| Enhanced stagnation detection | Available |
| Goal tracking | Available |
| Token cost tracking | Available |

## Architecture

```
Mission Coordinator (Claude Haiku 4.5) — plans, delegates, synthesizes
├── Corridor Designer (Qwen 3 VL) — creates H3 digital rails
│   Tools: create_corridor, validate_corridor, list_corridors
├── Flight Guardian (Claude Haiku 4.5) — monitors, detects, corrects
│   Tools: check_block_membership, step_simulation, generate_correction
└── Compliance Recorder (Qwen 3 VL) — verifies, certifies
    Tools: verify_chain_integrity, generate_certificate
```

### Multi-LLM Strategy (AWS Bedrock)

| Role | Model | Why |
|---|---|---|
| Coordinator/Guardian | Claude Haiku 4.5 | Safety-critical reasoning, reliable, can't be fine-tuned |
| Designer/Compliance | Qwen 3 VL 235B | Good tool calling, cost-effective (~3x cheaper) |

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/raviakasapu/akasa-corridor-agent.git
cd akasa-corridor-agent
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install h3 boto3 fastapi uvicorn httpx pydantic
pip install -e /path/to/auto-ai-agent-framework/agent-framework-pypi

# 3. Set environment (or copy .env.example)
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1

# 4. Run single-agent test (3 agents, sequential)
python tests/test_full_mission.py

# 5. Run multi-agent test (framework orchestration)
python tests/test_multi_agent_mission.py
```

## Project Structure

```
akasa-corridor-agent/
├── app/
│   └── sdk_agent/
│       ├── agent.py                    # Agent factory (Guardian, Designer, Compliance)
│       └── tools/
│           ├── registry.py             # @tool decorator + registry
│           ├── simulation/
│           │   ├── engine.py           # DroneSimulator, FlightLedger, H3 geocode
│           │   └── drone_tools.py      # 10 simulation tools
│           ├── corridor/
│           │   └── management.py       # 4 corridor tools
│           └── compliance/
│               └── ledger_tools.py     # 4 compliance tools
├── tests/
│   ├── test_real_llm_flight.py         # Raw LLM + tools (12 iterations, 48K tokens)
│   ├── test_full_mission.py            # SingleAgent orchestration (3 agents, 59K tokens)
│   └── test_multi_agent_mission.py     # Multi-agent framework (SequentialPattern, SharedMemory)
├── .env                                # Bedrock credentials + model config
├── .gitignore
└── README.md
```

## Test Results

### Single-Agent Orchestration (`test_full_mission.py`)
```
Total time:     54.0s
Iterations:     18
Tool calls:     20
Tokens:         59,797 (Designer: 3K, Guardian: 49K, Compliance: 7K)
Conformance:    0.6
Chain integrity: VALID
Certificate:    CERT-6C5A7784
```

### Multi-Agent Framework (`test_multi_agent_mission.py`)
```
Total time:     38.3s
Stages:         3/3 SUCCESS
Agents:         corridor-designer, flight-guardian, compliance-recorder
SharedMemory:   corridor_id + flight_id passed between stages
Chain integrity: VALID
```

## 18 Tools

### Simulation (10)
| Tool | Description |
|---|---|
| `start_simulation` | Start drone on corridor |
| `step_simulation` | Advance by 0.5s |
| `get_drone_position` | Current lat/lon/alt |
| `check_block_membership` | **Core patent:** resolve position → H3 cell → compare to assigned |
| `generate_correction` | Steer drone back to assigned block |
| `inject_wind_gust` | Simulate wind disruption |
| `inject_gps_noise` | Simulate GPS degradation |
| `get_flight_telemetry` | Full telemetry snapshot |
| `complete_flight` | End flight normally |
| `emergency_land` | Abort flight |

### Corridor (4)
| Tool | Description |
|---|---|
| `create_corridor` | Create H3 digital rail between two points |
| `list_corridors` | List all corridors |
| `get_corridor_detail` | Full corridor info |
| `validate_corridor` | Safety validation |

### Compliance (4)
| Tool | Description |
|---|---|
| `get_flight_events` | Get ledger events |
| `verify_chain_integrity` | Verify SHA-256 hash chain |
| `calculate_conformance_score` | Compute compliance ratio |
| `generate_certificate` | Generate Compliance Certificate |

## Related Repositories

- **[auto-ai-agent-framework](https://github.com/raviakasapu/auto-ai-agent-framework)** — The agent framework powering this system (v2.1 branch)
- **[patent_research_2025](https://github.com/raviakasapu/patent_research_2025)** — Patent prior art research and claim analysis
- **[drone_mvp](https://github.com/raviakasapu/drone_mvp)** — Original Ākāsā MVP PRD and architecture docs
