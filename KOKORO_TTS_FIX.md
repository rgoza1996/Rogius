# KokoroTTS Setup & Fix

## Architecture

The TTS system now uses a **proxy architecture**:

```
Frontend (Next.js) 
    ↓ HTTP POST /tts/speech
Python Backend (FastAPI at :8000)
    ↓ HTTP POST /v1/audio/speech (via Tailscale)
KokoroTTS Server on roggoz (:8880)
    ↓ Returns WAV audio
Python Backend streams audio to Frontend
    ↓ Auto cleanup on roggoz (handled by server)
```

**New Endpoints:**
- `POST /tts/speech` - Generate speech (returns audio/wav blob)
- `GET /tts/check` - Check if TTS server is reachable

## Problem
TTS endpoint at `http://100.71.89.62:8880/v1/audio/speech` is not reachable.

## Investigation Summary
SSH'd into roggoz@100.71.89.62 and found:

### Findings
1. **No system service**: `kokoro-tts.service` does not exist
2. **Python script exists**: `/home/roggoz/kokoro-server.py` found
3. **Model cached**: Kokoro-82M model and voices (af_bella, af_heart, etc.) exist in `~/.cache/huggingface/`
4. **Dependencies installed**: torch, kokoro, fastapi, uvicorn all installed
5. **Issue**: Server hangs when loading KPipeline on CPU (AMD Ryzen 7 5800X, no GPU)

### Root Cause
The Kokoro pipeline initialization takes too long on CPU-only machine. The model loading hangs indefinitely, preventing the server from starting.

## Solution

### Step 1: Start KokoroTTS Server on roggoz

Use the provided PowerShell script:
```powershell
# Check status
.\scripts\start-kokoro-server.ps1 -Status

# Start server
.\scripts\start-kokoro-server.ps1 -Start

# View logs
.\scripts\start-kokoro-server.ps1 -Logs
```

Or manually via SSH:
```bash
ssh roggoz@100.71.89.62
cd ~
screen -dmS kokoro python3 kokoro-server.py
# Wait 2-3 minutes for model loading
```

### Step 2: Restart Python Backend
After starting the Kokoro server, restart the Python API:
```powershell
.\scripts\stop-python-api.ps1
.\scripts\start-python-api.ps1
```

### Step 3: Verify TTS is Working

Check TTS status:
```powershell
curl http://localhost:8000/tts/check
```

Or use the Python Bridge in the frontend:
```typescript
const status = await pythonBridge.tts.check();
console.log(status.available); // Should be true
```

## Verification Commands

On remote machine (roggoz):
```bash
# Check if listening on port 8880
ss -tlnp | grep 8880

# Test locally
curl -X POST http://localhost:8880/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input": "Hello world", "voice": "af_bella"}' \
  --output test.wav
```

From Windows client (via Python backend):
```powershell
# Check TTS availability
curl http://localhost:8000/tts/check

# Generate speech through proxy
curl -X POST http://localhost:8000/tts/speech `
  -H "Content-Type: application/json" `
  -d '{"input": "Hello from Rogius", "voice": "af_bella"}' `
  --output test.wav
```

## Current Configuration
- **TTS Endpoint (Remote)**: `http://100.71.89.62:8880/v1/audio/speech`
- **TTS Proxy (Local)**: `http://localhost:8000/tts/speech`
- **Voice**: `af_bella`
- **Remote Machine**: AMD Ryzen 7 5800X (no GPU)
- **Tailscale**: Working (ping via DERP in ~40ms)

## Code Changes Made

### 1. Added TTS Routes to api_server.py
- `GET /tts/check` - Health check
- `POST /tts/speech` - Generate speech (proxies to roggoz)

### 2. Added TTS Methods to python-bridge.ts
- `pythonBridge.tts.check()` - Check TTS availability
- `pythonBridge.tts.generateSpeech(request)` - Generate speech

### 3. Updated useTTS.ts
- Changed to use `pythonBridge.tts.generateSpeech()` instead of direct fetch
- Updated `speakMessage()` signature to accept voice string instead of full config

### 4. Updated page.tsx
- Changed all `speakMessage()` calls to pass `chat.config.ttsVoice` instead of full config

## Audio File Cleanup

The KokoroTTS server on roggoz generates temporary WAV files. The current implementation does not persist files - they are streamed directly and cleaned up by the server. If you need explicit cleanup, the kokoro-server.py script should be modified to remove files after sending them.

## Troubleshooting

### "KokoroTTS server is not running"
The server needs to be started on roggoz. Use the PowerShell script or SSH manually.

### "TTS connection failed"
1. Check tailscale connection: `ping 100.71.89.62`
2. Verify server is running: `curl http://100.71.89.62:8880/v1/audio/speech` (should not timeout)
3. Check Python backend logs for errors

### Model loading hangs
On CPU-only machines, first startup takes 2-3 minutes. Use the logs command to watch progress:
```powershell
.\scripts\start-kokoro-server.ps1 -Logs
```
