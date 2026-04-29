# Python Backend Integration

The webapp can now use the TUI's Python modules as a backend via FastAPI HTTP API.

## Architecture

```
┌─────────────────┐     HTTP API      ┌──────────────────┐
│  Next.js Webapp │ ◄──────────────► │  FastAPI Python  │
│  (React/TS)     │   /api/python/*  │  (TUI modules)   │
└─────────────────┘                    └──────────────────┘
                                              │
                                              ▼
                                       ┌──────────────┐
                                       │ shell_runner │
                                       │ multistep    │
                                       │ ai_client    │
                                       │ settings     │
                                       └──────────────┘
```

## Quick Start

### 1. Start the Python API Server

```bash
# Using npm script
npm run python-api:start

# Or manually
cd src/tui
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Start the Webapp

```bash
# Full development mode (starts Python API + Next.js)
npm run dev:full

# Or just Next.js (if Python API already running)
npm run dev
```

### 3. Verify Connection

Visit: http://127.0.0.1:8000/health

Should return:
```json
{"status":"healthy","timestamp":"...","version":"1.0.0"}
```

## API Endpoints

### Health
- `GET /health` - Server health check

### Terminal
- `POST /terminal/execute` - Execute shell command
- `GET /terminal/history` - Get command history

### Multi-Step Plans
- `POST /multistep/create` - Create new plan
- `GET /multistep/status` - Get plan status
- `POST /multistep/execute` - Execute all steps
- `POST /multistep/execute-next` - Execute next step only
- `POST /multistep/clear` - Clear active plan

### AI Chat
- `POST /ai/chat` - Chat completion (non-streaming)
- `POST /ai/chat/stream` - Streaming chat (SSE)
- `GET /ai/models` - List available models

### Settings
- `GET /settings` - Get current settings
- `POST /settings` - Update settings

### System
- `GET /system/info` - System information

## Using from React

### Basic Terminal Command

```typescript
import { pythonBridge } from '@/lib/python-bridge'

const result = await pythonBridge.terminal.execute({
  command: 'ls -la',
  cwd: '/some/path'
})

console.log(result.stdout)
```

### Multi-Step Plan

```typescript
// Create plan
await pythonBridge.multistep.create({
  goal: 'Deploy app',
  steps: [
    { description: 'Build', command: 'npm run build' },
    { description: 'Test', command: 'npm test' },
    { description: 'Deploy', command: 'npm run deploy' }
  ]
})

// Execute
const result = await pythonBridge.multistep.execute()
console.log(`Completed ${result.completed}/${result.total} steps`)
```

### AI Chat Streaming

```typescript
await pythonBridge.ai.chatStream(
  {
    messages: [
      { role: 'user', content: 'Hello!' }
    ],
    stream: true
  },
  (chunk) => {
    // Handle streaming chunk
    console.log(chunk.content)
  },
  () => {
    // Stream complete
    console.log('Done!')
  }
)
```

## Features Shared with TUI

✅ **PowerShell-safe command execution** - Quotes/apostrophes handled automatically  
✅ **Multi-step plan execution** - Same logic as TUI  
✅ **AI streaming** - Real-time chat with tool calling  
✅ **Settings persistence** - Shared with TUI settings  
✅ **Command history** - Tracked by shell_runner  

## Files

### Python Backend
- `src/tui/api_server.py` - FastAPI application
- `src/tui/requirements-api.txt` - Python dependencies
- `src/tui/launcher.py` - Server start/stop functions

### Webapp Proxy Routes
- `src/app/api/python/terminal/route.ts`
- `src/app/api/python/multistep/route.ts`
- `src/app/api/python/ai/chat/route.ts`
- `src/app/api/python/settings/route.ts`
- `src/app/api/python/system/info/route.ts`
- `src/app/api/python/health/route.ts`

### TypeScript Client
- `src/lib/python-bridge.ts` - Main API client

### Scripts
- `scripts/start-python-api.ps1` - Start server
- `scripts/stop-python-api.ps1` - Stop server

## Environment Variables

```bash
# Optional: Change Python API URL
NEXT_PUBLIC_PYTHON_API_URL=http://127.0.0.1:8000
PYTHON_API_URL=http://127.0.0.1:8000
```

## Both Can Run Together

- TUI: `python tui.py` (standalone)
- Webapp: `npm run dev` (uses Python backend)
- Both share the same settings and can execute plans

## API Documentation

When server is running, visit:
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
