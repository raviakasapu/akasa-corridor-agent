# Akasa Corridor Dashboard

Real-time drone corridor monitoring dashboard built with React, Vite, and Leaflet.

## Architecture

```
Zustand Store (missionStore)
  ├── mission   { jobId, status, mode, stats }
  ├── drone     { position, status, blockIndex, deviation }
  ├── corridor  { corridorId, name, blockCount }
  ├── agent     { status, thinking, toolCalls, content }
  └── events[]  { event, data, timestamp }

WebSocket (/ws/agent)
  └── useMission hook parses events → updates store → components re-render
```

## File Structure

```
src/
├── main.tsx                    React mount
├── App.tsx                     Root → Dashboard
├── index.css                   Tailwind + Leaflet dark mode
├── types/index.ts              Mission, Drone, Corridor, Agent, EventType
├── store/missionStore.ts       Zustand state + actions
├── utils/
│   ├── websocket.ts            Singleton WS, auto-reconnect, handler registry
│   └── formatters.ts           Time, duration, truncate helpers
├── hooks/
│   ├── useWebSocket.ts         Connect/cleanup lifecycle
│   └── useMission.ts           Event parser → store updater
└── components/
    ├── Dashboard.tsx            2/3 map + 1/3 feed layout
    ├── DroneMap.tsx             Leaflet dark tiles, drone/corridor markers
    ├── EventFeed.tsx            Color-coded scrolling event stream
    ├── AgentPanel.tsx           Agent status, thinking, stats, recent tools
    ├── MissionControl.tsx       Presets, mode select, start/stop buttons
    ├── StatusBadge.tsx          Animated pulse badge for active states
    └── ToolExecutor.tsx         Tool call + result visualization cards
```

## Setup

```bash
cd frontend
npm install
npm run dev       # http://localhost:3000
```

The Vite dev server proxies `/api` and `/ws` to the backend at `localhost:8052`.

## Environment

No frontend env vars needed for local development. The Vite proxy handles routing.

For production builds, set in `.env`:

```
VITE_API_URL=https://your-backend.railway.app
VITE_WS_URL=wss://your-backend.railway.app
```

## Connecting to Backend

1. Start the backend: `uvicorn app.main:app --port 8052 --reload`
2. Start the frontend: `cd frontend && npm run dev`
3. Open `http://localhost:3000`
4. The dashboard auto-connects via WebSocket to `/ws/agent`

## Components

| Component | Purpose |
|-----------|---------|
| **Dashboard** | Main layout — header with mission info, 2/3 map + 1/3 sidebar |
| **DroneMap** | Leaflet map with dark CartoDB tiles, drone marker (blue dot with glow), corridor path (dashed blue line), start/end markers |
| **EventFeed** | Auto-scrolling event list with Framer Motion animations. Events colored by type: purple=thinking, blue=tool_call, green=tool_done, red=error |
| **AgentPanel** | Shows agent name, status badge, thinking text, tool/iteration/duration stats, recent tool results |
| **MissionControl** | Mode selector (single/guardian/designer/compliance), preset missions, custom message textarea, start/reset buttons, connection indicator |
| **StatusBadge** | Rounded badge with animated pulse dot for active states (running, thinking, executing) |
| **ToolExecutor** | Cards showing recent tool calls (blue) and results (green/red) with args and summaries |

## Real-Time Event Flow

```
Backend Agent
  │ async for event in agent.run(message):
  ▼
FastAPI WebSocket (/ws/agent)
  │ await websocket.send_json(frontend_event)
  ▼
Browser WebSocket (utils/websocket.ts)
  │ conn.handlers.forEach(h => h(parsed))
  ▼
useMission hook (hooks/useMission.ts)
  │ switch(event.event) → store.addToolCall() / store.updateDrone() / ...
  ▼
Zustand Store (store/missionStore.ts)
  │ state update triggers re-render
  ▼
React Components
  ├── DroneMap       drone position moves on map
  ├── EventFeed      new event animates in
  ├── AgentPanel     status/thinking updates
  └── MissionControl status badge changes
```

## Testing

1. Start backend and frontend
2. Click "Start Mission" with the "Full Mission (SF → Oakland)" preset
3. Watch:
   - Map shows corridor path and drone position updating
   - Event feed shows tool_call → tool_done events streaming
   - Agent panel shows thinking → executing → complete transitions
   - Status badge pulses during execution, turns green on complete
