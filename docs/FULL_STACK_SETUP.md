# Full Stack Setup

## Prerequisites

- Python 3.10+
- Node.js 18+
- AWS Bedrock access (for LLM calls)
- auto-ai-agent-framework installed locally

## 1. Backend Setup

```bash
cd akasa-corridor-agent

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
pip install -e /path/to/auto-ai-agent-framework/agent-framework-pypi

# Configure environment
cp .env.example .env
# Edit .env:
#   AWS_ACCESS_KEY_ID=your_key
#   AWS_SECRET_ACCESS_KEY=your_secret
#   AWS_REGION=us-east-1

# Start backend
uvicorn app.main:app --host localhost --port 8052 --reload
```

Verify: `curl http://localhost:8052/health`

Expected:
```json
{"status": "healthy", "version": "1.0.0", "agent_framework": "2.x.x"}
```

## 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:3000`. Vite proxies `/api` and `/ws` to backend at `:8052`.

## 3. Running Both Together

Terminal 1 (backend):
```bash
cd akasa-corridor-agent
source .venv/bin/activate
uvicorn app.main:app --port 8052 --reload
```

Terminal 2 (frontend):
```bash
cd akasa-corridor-agent/frontend
npm run dev
```

Open `http://localhost:3000` in browser.

## 4. Testing the Full Stack

### Verify connectivity
1. Open browser to `http://localhost:3000`
2. Check WiFi icon in Mission Control — should be green
3. Browser console should show `WebSocket connected`

### Run a mission
1. Select "Full Mission (SF → Oakland)" preset
2. Click "Start Mission"
3. Watch:
   - **Map**: Corridor path appears, drone marker moves along it
   - **Event Feed**: Events stream in (tool_call → tool_done → content)
   - **Agent Panel**: Status transitions (thinking → executing → complete)
   - **Header**: Corridor ID, flight ID, drone status appear

### Verify backend tools
```bash
curl http://localhost:8052/api/v1/tools | python3 -m json.tool
# Should list 18 tools

curl http://localhost:8052/api/v1/agents | python3 -m json.tool
# Should list 5 YAML configs
```

### Test sync endpoint
```bash
curl -X POST http://localhost:8052/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"job_id":"test","message":"List all corridors"}'
```

## 5. Troubleshooting

### WebSocket not connecting
- Check backend is running on port 8052
- Check Vite proxy config in `frontend/vite.config.ts`
- Check browser console for WS errors
- Verify `/ws/agent` endpoint: `wscat -c ws://localhost:8052/ws/agent`

### "SDK Agent not available"
- Ensure `agent_framework` is installed: `pip show auto-ai-agent-framework`
- Check backend startup logs for import errors

### Tools not registering (0 tools)
- Ensure `app/sdk_agent/__init__.py` imports all tool modules
- Check: `curl http://localhost:8052/api/v1/tools` should show `count: 18`

### Map not rendering
- Leaflet CSS is loaded from CDN in `index.html`
- Check browser console for tile loading errors
- CartoDB tiles require internet access

### Agent errors / timeouts
- Check AWS credentials in `.env`
- Verify Bedrock model access: `GUARDIAN_MODEL`, `WORKER_MODEL`
- Check backend logs for Bedrock API errors
- Increase `max_iterations` if agent stops early

## 6. Production Build

```bash
cd frontend
npm run build    # outputs to frontend/dist/

# Serve with any static server:
npx serve dist
```

For Railway/Vercel deployment, see `docs/FASTAPI_MULTIAGENT_ARCHITECTURE.md`.
