# Dashboard Features

## Overview

The Akasa Corridor Dashboard is a single-page React app that connects to the backend via WebSocket and renders real-time drone corridor operations. The layout is split into a map area (left, 2/3) and a monitoring sidebar (right, 1/3), with a header showing active mission identifiers.

```
┌────────────────────────────────────────────────────────────────┐
│  Header: corridor ID • flight ID • drone status • certificate  │
├──────────────────────────────────┬─────────────────────────────┤
│                                  │  Agent Panel                │
│  Mission Control                 │  ├─ name + status badge     │
│  ├─ mode selector                │  ├─ thinking text           │
│  ├─ preset dropdown              │  ├─ stats (tools/dur/iter)  │
│  ├─ message textarea             │  └─ recent tool results     │
│  └─ start / reset                │                             │
│                                  │  Tool Executor              │
│  ┌────────────────────────────┐  │  ├─ call cards (blue)       │
│  │                            │  │  └─ result cards (green/red)│
│  │       Leaflet Map          │  │                             │
│  │   corridor + drone + tiles │  │  Event Feed                 │
│  │                            │  │  ├─ timestamped events      │
│  └────────────────────────────┘  │  └─ color-coded by type     │
└──────────────────────────────────┴─────────────────────────────┘
```

## Real-Time Drone Monitoring

**Component:** `DroneMap.tsx`

The map uses CartoDB dark tiles and renders:

- **Drone marker**: Blue circle with white border and glow shadow. Position updates every time `check_block_membership`, `step_simulation`, or `get_drone_position` returns a result. The map auto-pans to follow the drone.
- **Block progress**: Header shows `Block N/M` and deviation distance if deviating.

Data source: `tool_done` events for simulation tools. The `useMission` hook extracts `position`, `block_index`, `total_blocks`, `status`, and `deviation_meters` from the result dict and writes them to `store.drone`.

## Event Feed

**Component:** `EventFeed.tsx`

A scrollable panel that appends every WebSocket event with Framer Motion entrance animations. Auto-scrolls to the bottom on new events. Capped at 200 events in the store.

Color scheme (left border):

| Color | Event Type | Example |
|-------|-----------|---------|
| Gray | `status` | Starting... |
| Purple | `thinking` | Processing... |
| Blue | `tool_call` | `create_corridor({name, start_lat, ...})` |
| Green | `tool_done` | `create_corridor OK: Created corridor COR-A1B2` |
| White | `content` | Agent final response text |
| Green | `complete` | `4 tools, 12.3s` |
| Red | `error` | Tool execution failed |
| Yellow | `simulation_updated` | Updated: step_simulation |

Each row shows: `[HH:MM:SS] Label summary`

## Agent Panel

**Component:** `AgentPanel.tsx`

Displays the active agent's state:

- **Header**: Agent name + animated `StatusBadge` (idle/thinking/executing/complete/error)
- **Thinking box**: Purple background, shows current reasoning text from `thinking` events
- **Response box**: Gray background, shows final `content` text after completion
- **Stats grid**: Three metric cards:
  - Tools: total tool calls completed
  - Duration: execution time (from `complete` event)
  - Iterations: LLM iterations (from `complete` event)
- **Recent tools**: Last 5 tool results with success/fail color coding and summary text

## Mission Control

**Component:** `MissionControl.tsx`

Controls for launching and managing missions:

- **Connection indicator**: Green WiFi icon when WebSocket is connected, red when disconnected
- **Status badge**: Shows current mission status with pulse animation when active
- **Mode selector**: `single` (all 18 tools), `guardian` (simulation only), `designer` (corridor only), `compliance` (audit only)
- **Preset dropdown**: Three built-in missions:
  1. Full Mission (SF to Oakland) — create corridor, fly, certify
  2. Create Corridor Only — Delhi to Agra
  3. List Corridors — simple query
- **Message textarea**: Editable mission instructions (presets populate this)
- **Start button**: Disabled when disconnected or already running
- **Reset button**: Clears all state (mission, drone, corridor, events, agent)

## Corridor Visualization

**Component:** `DroneMap.tsx`

When a corridor is created:
- Dashed blue polyline drawn between start and end points
- Green circle marker at start, red circle at end
- Popup on each marker shows corridor name

The corridor data is extracted from the `create_corridor` tool result in `useMission`.

Future: H3 hex cells rendered as polygons using h3-js, showing the actual digital rail blocks.

## Conformance Monitoring

Deviation is tracked through the drone state:

- `drone.status` shows `NOMINAL` (green in header) or `DEVIATING` (red)
- `drone.deviationMeters` shows distance from assigned block
- When deviating, the map header shows `DEVIATING Xm` in red
- `generate_correction` tool results appear in the event feed and agent panel
- Conformance score from `calculate_conformance_score` appears in tool results

The `complete` event marks mission end, and certificate ID appears in the header when `generate_certificate` succeeds.

## Multi-Agent Orchestration View

The mode selector in MissionControl lets users run specific agent roles:

| Mode | Agent | Tools Available |
|------|-------|----------------|
| single | Full agent | All 18 |
| designer | Corridor Designer | create, list, detail, validate corridor |
| guardian | Flight Guardian | start, step, check, correct, complete, emergency, wind, gps, telemetry, position |
| compliance | Compliance Recorder | events, chain integrity, score, certificate, telemetry |

In orchestrated mode (future), the event feed and agent panel would show phase transitions:
```
[Phase 1] Designer: Creating corridor...
[Phase 2] Guardian: Monitoring flight...
[Phase 3] Compliance: Generating certificate...
```

## Performance Metrics

Visible in the Agent Panel stats grid after mission completion:

- **Tool calls**: Total number of tools executed
- **Duration**: Wall-clock time from start to complete
- **Iterations**: Number of LLM reasoning loops

In the event feed, each `tool_done` shows the tool name and result summary, giving a chronological trace of execution.

Future: Token usage display (input/output/cached tokens from the `complete` event's `usage` field).
