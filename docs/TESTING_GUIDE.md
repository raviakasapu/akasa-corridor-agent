# Testing Guide

## Local Setup

```bash
# Terminal 1 — Backend
cd akasa-corridor-agent
source .venv/bin/activate
uvicorn app.main:app --port 8052 --reload

# Terminal 2 — Frontend
cd akasa-corridor-agent/frontend
npm install   # first time only
npm run dev   # http://localhost:3000
```

Verify backend: `curl http://localhost:8052/health`
Verify tools: `curl http://localhost:8052/api/v1/tools | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])"`
Expected: `18`

---

## Test Scenarios

### 1. Single-Agent Full Mission

**Steps:**
1. Open `http://localhost:3000`
2. Confirm green WiFi icon
3. Mode: `Single Agent`
4. Preset: "Full Mission (SF → Oakland)"
5. Click "Start Mission"

**Expected events in feed:**
```
tool_call   create_corridor({name: "...", start_lat: 37.77, ...})
tool_done   create_corridor OK: Created corridor COR-XXXX with N blocks
tool_call   validate_corridor({corridor_id: "COR-XXXX"})
tool_done   validate_corridor OK: Corridor is valid
tool_call   start_simulation({corridor_id: "COR-XXXX"})
tool_done   start_simulation OK: flight_id=FLT-YYYY
tool_call   check_block_membership({flight_id: "FLT-YYYY"})
tool_done   check_block_membership OK: status=NOMINAL
tool_call   step_simulation(...)
...repeat check/step cycles...
tool_call   complete_flight(...)
tool_done   complete_flight OK: status=COMPLETED
tool_call   verify_chain_integrity(...)
tool_done   verify_chain_integrity OK: valid=true
tool_call   calculate_conformance_score(...)
tool_call   generate_certificate(...)
tool_done   generate_certificate OK: certificate_id=CERT-ZZZZ
content     Agent summary text
complete    N tools, X.Xs
```

**Verify:**
- Map shows corridor line and drone marker
- Header shows corridor ID, flight ID, drone status
- Agent panel shows iterations, duration, tool count
- Status badge transitions: idle → running → complete (green)

### 2. Corridor Design Only

**Steps:**
1. Mode: `Designer Only`
2. Preset: "Create Corridor Only"
3. Start

**Expected:**
- Only corridor tools called (create_corridor, validate_corridor)
- Map shows corridor path
- No simulation events

### 3. WebSocket Streaming Verification

**Steps:**
1. Open browser DevTools → Network → WS tab
2. Start any mission
3. Watch WebSocket frames

**Expected frame sequence:**
```json
← {"event":"connected","data":{"agent":"akasa-corridor-agent"}}
→ {"action":"set_context","job_id":"...","mode":"single"}
← {"event":"context_set","data":{"job_id":"...","mode":"single"}}
→ {"action":"execute","job_id":"...","message":"..."}
← {"event":"status","data":{"message":"Starting..."}}
← {"event":"tool_call","data":{"tool":"create_corridor","args":{...}}}
← {"event":"tool_done","data":{"tool":"create_corridor","success":true,...}}
...
← {"event":"complete","data":{"duration_s":...,"tool_calls":...}}
```

### 4. Error Handling

**Test: Invalid tool arguments**
```bash
curl -X POST http://localhost:8052/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"job_id":"err-test","message":"Start a simulation on corridor NONEXISTENT"}'
```

**Expected:** Agent receives tool error, may retry or report failure. Event feed shows red error events.

**Test: No AWS credentials**
Remove `AWS_ACCESS_KEY_ID` from `.env` and restart backend.

**Expected:** Backend logs Bedrock connection error. Frontend shows error event in feed.

### 5. Drone Deviation Detection

**Steps:**
1. Start a full mission
2. Watch for `check_block_membership` results

**Expected when nominal:**
```
tool_done  check_block_membership OK: status=NOMINAL, deviation_meters=0.0
```

**Expected when deviating (wind/GPS injected by agent):**
```
tool_done  check_block_membership OK: status=DEVIATING, deviation_meters=45.2
tool_call  generate_correction({flight_id: "..."})
tool_done  generate_correction OK: correction applied
```

**Verify in UI:**
- Header shows `DEVIATING 45m` in red text
- Event feed shows correction tool calls
- Drone marker position may shift slightly on map

### 6. Compliance Verification

**Steps:**
1. Complete a full mission (or use compliance mode after a flight exists)
2. Watch compliance tool sequence

**Expected:**
```
tool_call  get_flight_events({flight_id: "..."})
tool_done  get_flight_events OK: N events returned
tool_call  verify_chain_integrity({flight_id: "..."})
tool_done  verify_chain_integrity OK: valid=true, chain_length=N
tool_call  calculate_conformance_score({flight_id: "..."})
tool_done  calculate_conformance_score OK: score=0.85
tool_call  generate_certificate({flight_id: "..."})
tool_done  generate_certificate OK: certificate_id=CERT-XXXX, score=0.85
```

**Verify:**
- Certificate ID appears in header (green, with FileCheck icon)
- Agent panel shows all 4 compliance tools in recent results

---

## Backend-Only Testing

### Sync endpoint
```bash
curl -X POST http://localhost:8052/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"job_id":"test-1","message":"List all corridors","max_iterations":5}'
```

### SSE streaming
```bash
curl -N -X POST http://localhost:8052/api/v1/execute/stream \
  -H "Content-Type: application/json" \
  -d '{"job_id":"test-2","message":"Create a corridor from (37.77,-122.42) to (37.80,-122.27)"}'
```

### Tool listing
```bash
curl http://localhost:8052/api/v1/tools
curl http://localhost:8052/api/v1/agents
```

### Existing test scripts
```bash
python tests/test_full_mission.py            # 3-agent sequential
python tests/test_multi_agent_mission.py     # Framework orchestration
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Red WiFi icon | Backend not running or wrong port | Start backend on 8052 |
| 0 tools returned | Tool modules not imported | Check `app/sdk_agent/__init__.py` |
| "SDK Agent not available" | `agent_framework` not installed | `pip install -e /path/to/framework` |
| Map blank | No internet (CDN tiles) | Check network, or use local tiles |
| Agent timeout | AWS credentials missing | Set in `.env` |
| Drone not moving on map | Tool results not parsed | Check `useMission.ts` tool extraction |
| Events not appearing | WebSocket disconnected | Check browser console, refresh |
