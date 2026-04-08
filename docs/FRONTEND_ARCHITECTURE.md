# Frontend Architecture

## Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Build | Vite 5 | Fast HMR, TypeScript, proxy config |
| UI | React 18 | Component rendering |
| Styling | Tailwind CSS 3.4 | Utility-first dark theme |
| State | Zustand 4.5 | Lightweight reactive store |
| Maps | Leaflet + react-leaflet | Corridor/drone visualization |
| Animation | Framer Motion 11 | Event feed transitions, card entrances |
| Icons | Lucide React | Consistent icon set |
| HTTP | Axios | REST fallback (future) |

## State Management

Zustand store in `src/store/missionStore.ts`:

```typescript
interface MissionState {
  // Connection
  isConnected: boolean

  // Core entities
  mission: Mission       // { jobId, status, mode, startTime, stats }
  drone: Drone | null    // { flightId, position, status, blockIndex, deviation }
  corridor: Corridor | null  // { corridorId, name, blockCount, rail }
  agent: Agent           // { name, status, thinking, toolCalls, content }

  // Events (capped at 200)
  events: AgentEvent[]

  // Actions
  setMissionStatus(status)
  updateDrone(partial)
  setCorridor(corridor)
  addToolCall(tc)
  addToolResult(tr)
  setAgentThinking(text)
  setAgentContent(text)
  resetMission()
}
```

Why Zustand over Context: no provider nesting, direct subscription outside React, built-in immer-free updates, minimal boilerplate.

## WebSocket Protocol

### Connection

```
Browser → ws://localhost:3000/ws/agent (proxied to :8052)
Server → {"event":"connected","data":{"agent":"akasa-corridor-agent"}}
```

### Client Messages

```json
{"action": "set_context", "job_id": "mission-001", "mode": "single"}
{"action": "execute", "job_id": "mission-001", "message": "Create a corridor..."}
{"action": "ping"}
```

### Server Events

| Event | Data | Store Action |
|-------|------|-------------|
| `connected` | `{agent, version}` | `setConnected(true)` |
| `status` | `{message}` | `updateAgent({status:"thinking"})` |
| `thinking` | `{message, iteration}` | `setAgentThinking(message)` |
| `tool_call` | `{tool, args, tool_index}` | `addToolCall(tc)` |
| `tool_done` | `{tool, success, summary, result}` | `addToolResult(tr)`, extract drone/corridor |
| `content` | `{text}` | `setAgentContent(text)` |
| `complete` | `{duration_s, iterations, tool_calls}` | `updateAgent({...}), setMissionStatus("complete")` |
| `error` | `{message}` | `updateAgent({status:"error"})` |
| `simulation_updated` | `{tool}` | (triggers re-render via drone state) |

### Auto-Reconnect

`utils/websocket.ts` reconnects after 3 seconds on close. The `useWebSocket` hook polls connection state every 2 seconds to update the UI indicator.

## Component Hierarchy

```
App
└── Dashboard
    ├── Header (corridor ID, flight ID, certificate, drone status)
    ├── Left Panel (flex-[2])
    │   ├── MissionControl
    │   │   ├── Mode selector (single/guardian/designer/compliance)
    │   │   ├── Preset selector (full mission / corridor only / list)
    │   │   ├── Message textarea
    │   │   └── Start / Reset buttons + StatusBadge + WiFi indicator
    │   └── DroneMap
    │       ├── CartoDB dark tiles
    │       ├── Corridor path (dashed polyline)
    │       ├── Start marker (green) + End marker (red)
    │       ├── Drone marker (blue with glow)
    │       └── MapUpdater (auto-pan to drone)
    └── Right Panel (flex-[1], 360-440px)
        ├── AgentPanel
        │   ├── Name + StatusBadge
        │   ├── Thinking display (purple box)
        │   ├── Response display (gray box)
        │   ├── Stats grid (tools / duration / iterations)
        │   └── Recent tool results list
        ├── ToolExecutor
        │   ├── ToolCallCard (blue, args preview)
        │   └── ToolResultCard (green/red, summary)
        └── EventFeed
            └── Scrollable list with AnimatePresence
                └── Event row (timestamp + label + summary)
```

## Real-Time Data Flow

```
Agent tool execution
  │
  ▼
Backend: tool_done event with result dict
  │ e.g. check_block_membership → {status, deviation_meters, position, block_index}
  ▼
WebSocket: JSON sent to browser
  ▼
useMission hook: parseEvent()
  │
  ├─ addToolResult(tr)          → agent.toolResults updates → AgentPanel re-renders
  │
  ├─ updateDrone({position,...}) → drone state updates → DroneMap marker moves
  │                                                     → Header status updates
  │
  ├─ setCorridor({...})         → corridor state updates → DroneMap path draws
  │
  └─ addEvent(e)                → events[] grows → EventFeed scrolls to bottom
```

## Drone Visualization

### Map Setup
- **Tiles**: CartoDB dark_all (`dark_all/{z}/{x}/{y}{r}.png`)
- **Default center**: SF Bay Area (37.79, -122.35), zoom 12
- **Auto-pan**: `MapUpdater` component uses `useMap()` to follow drone

### Markers
- **Drone**: Blue circle (20px) with white border and blue box-shadow glow
- **Start**: Green circle (14px)
- **End**: Red circle (14px)
- **Corridor**: Dashed blue polyline (weight 3, opacity 0.6)

### Drone State Extraction
The `useMission` hook extracts drone position from `tool_done` events for these tools:
- `check_block_membership` → position, status, deviation, block index
- `step_simulation` → position update
- `get_drone_position` → full position snapshot

## Event Feed

Color coding via left border:
- **Gray** (status): Starting, idle messages
- **Purple** (thinking): Agent reasoning
- **Blue** (tool_call): Tool invocation with args
- **Green** (tool_done): Successful tool result
- **Red** (error): Failures
- **Yellow** (simulation_updated): Sim state changes

Each event shows: `[HH:MM:SS] Label summary_text`

Capped at 200 events in store (oldest trimmed).

## Performance Considerations

- **Event cap**: Store keeps max 200 events to prevent memory growth
- **Selective renders**: Zustand's selector pattern means components only re-render when their slice changes
- **Map updates**: `MapUpdater` only triggers `setView` when drone position actually changes
- **AnimatePresence**: `initial={false}` prevents animation of existing items on mount
- **WS singleton**: One connection shared across all hooks via handler registry

## Future Enhancements

- **H3 hex overlay**: Render actual H3 cells on the map using h3-js + leaflet polygons
- **Corridor rail visualization**: Draw each block of the digital rail as a hex cell
- **Flight trail**: Show drone path history as a fading polyline
- **Multi-drone**: Support concurrent flights on different corridors
- **Mission history**: Persist completed missions, replay events
- **Certificate viewer**: Formatted compliance certificate display
- **Telemetry charts**: Real-time conformance score, altitude, speed graphs
- **Dark/light theme toggle**
- **Mobile responsive layout**
