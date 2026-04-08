# Quick Start (5 minutes)

## Backend

```bash
source .venv/bin/activate
cp .env.example .env        # add AWS keys
uvicorn app.main:app --port 8052 --reload
```

Verify: `curl localhost:8052/health`

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Use

1. Open **http://localhost:3000**
2. Green WiFi icon = connected
3. Click **Start Mission**
4. Watch: map updates, events stream, agent executes tools

## Test from CLI

```bash
# List tools (should be 18)
curl localhost:8052/api/v1/tools | python3 -c "import sys,json;print(json.load(sys.stdin)['count'])"

# Run a mission
curl -X POST localhost:8052/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"job_id":"q1","message":"List all corridors"}'
```
