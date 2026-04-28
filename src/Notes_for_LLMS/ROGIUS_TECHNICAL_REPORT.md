# Rogius Technical Report
## Comprehensive Architecture & Engineering Documentation

**Version:** 1.0  
**Date:** April 23, 2026  
**Project:** Rogius - AI-Powered Agentic Task Execution System

---

## 1. Executive Summary

Rogius is a **multi-agent AI system** that orchestrates complex tasks through a coordinated pipeline of specialized agents. It provides both a **web interface** (Next.js/React) and a **terminal interface** (Python TUI) for interacting with a local or remote LLM to execute multi-step plans with terminal integration.

### Key Differentiators
- **6-Agent Architecture**: Investigator → Planner → Executor → Verifier → Reporter, orchestrated by RogiusMainAgent
- **Self-Healing Execution**: Automatic retry with failure classification and targeted fixes
- **RAG Integration**: Local codebase indexing for context-aware responses
- **Dual Interface**: Webapp and TUI with feature parity
- **Streaming-First**: Real-time progress updates via SSE

---

## 2. System Objectives

### Primary Goals
1. **Autonomous Task Execution**: Convert natural language goals into executed terminal commands
2. **Cross-Platform Support**: Windows (PowerShell) and Linux/macOS (Bash) compatibility
3. **Fault Tolerance**: Self-correcting execution with retry loops and replanning
4. **Transparency**: Full visibility into agent reasoning and execution steps
5. **Local-First**: Runs against local LLMs (LM Studio, Ollama) without cloud dependency

### Use Cases
- File system operations (create, move, delete, search)
- Development environment setup
- Code generation and modification
- System administration tasks
- Project analysis and documentation

---

## 3. Architecture Overview

### 3.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERFACES                                 │
├─────────────────────────────┬───────────────────────────────────────────────┤
│      WEBAPP (Next.js)       │         TUI (Python/Textual)                │
│  ┌─────────────────────┐    │    ┌─────────────────────────────────────┐  │
│  │  React Components   │    │    │  Textual Widgets                    │  │
│  │  - Chat Interface   │    │    │  - ChatPane                         │  │
│  │  - Agent Tracker    │    │    │  - PlanWidget                       │  │
│  │  - Settings Modal   │    │    │  - TerminalWidget                   │  │
│  └──────────┬──────────┘    │    └──────────────┬──────────────────────┘  │
│             │               │                     │                       │
│  ┌──────────▼──────────┐    │    ┌──────────────▼──────────────────────┐  │
│  │  Python API Bridge  │◄───┼────┤  FastAPI Server (api_server.py)       │  │
│  │  (python-bridge.ts) │    │    │  - REST endpoints                     │  │
│  └──────────┬──────────┘    │    │  - SSE streaming                      │  │
└─────────────┼───────────────┘    └──────────────┬──────────────────────┘  │
              │                                     │                        │
              └─────────────────────────────────────┘                        │
                                │                                          │
              ┌─────────────────▼──────────────────┐                       │
              │      MULTI-AGENT ORCHESTRATION    │                       │
              │         (subagents package)       │                       │
              │  ┌─────────┐  ┌─────────┐        │                       │
              │  │Investiga│  │ Planner │        │                       │
              │  │  tor    │  │         │        │                       │
              │  └────┬────┘  └────┬────┘        │                       │
              │       │            │             │                       │
              │  ┌────▼────────────▼────┐        │                       │
              │  │   RogiusMainAgent    │        │                       │
              │  │    (Orchestrator)    │        │                       │
              │  └────┬────────────┬───┘        │                       │
              │       │            │             │                       │
              │  ┌────▼────┐  ┌────▼────┐       │                       │
              │  │ Executor│  │ Verifier│       │                       │
              │  │         │  │         │       │                       │
              │  └────┬────┘  └─────────┘       │                       │
              │       │                        │                       │
              │  ┌────▼────┐                   │                       │
              │  │ Reporter│                   │                       │
              │  │         │                   │                       │
              │  └─────────┘                   │                       │
              └──────────┬─────────────────────┘                       │
                         │                                              │
              ┌──────────▼──────────────────────┐                     │
              │      TOOLS & INTEGRATIONS        │                     │
              │  ┌─────────┐ ┌─────────┐       │                     │
              │  │ Terminal│ │ Web     │       │                     │
              │  │ Shell   │ │ Search  │       │                     │
              │  └─────────┘ └─────────┘       │                     │
              │  ┌─────────┐ ┌─────────┐       │                     │
              │  │ RAG     │ │ TTS     │       │                     │
              │  │ Search  │ │ (Kokoro)│       │                     │
              │  └─────────┘ └─────────┘       │                     │
              └──────────────────────────────────┘                     │
                                                                       │
              ┌──────────────────────────────────┐                    │
              │      LLM PROVIDER                │◄───────────────────┘
              │  (LM Studio / Ollama / OpenAI)   │
              └──────────────────────────────────┘
```

### 3.2 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 14.2, React 18, TypeScript | Web interface |
| **Styling** | Tailwind CSS, Lucide icons | UI components |
| **TUI** | Python 3.11+, Textual | Terminal interface |
| **API** | FastAPI, uvicorn | Python HTTP server |
| **AI/ML** | PyTorch, Transformers, Tokenizers | Local inference support |
| **RAG** | LlamaIndex, Nomic embeddings | Codebase search |
| **Audio** | Kokoro TTS (remote) | Text-to-speech |

---

## 4. Multi-Agent System (Core Architecture)

The multi-agent system is the heart of Rogius. It implements a **pipeline architecture** with feedback loops for self-correction.

### 4.1 Agent Definitions

| Agent | Role | Responsibility |
|-------|------|----------------|
| **RogiusMainAgent** | Project Manager | Orchestrates workflow, manages state, coordinates all other agents |
| **InvestigatorAgent** | Environment Scout | Probes OS, shell, files, available commands; performs web/RAG search |
| **PlannerAgent** | Strategy Creator | Creates step-by-step execution plan from goal + context |
| **ExecutorAgent** | Command Generator | Translates logical steps into OS-specific terminal commands |
| **VerifierAgent** | QA Tester | Evaluates execution results, classifies failures, routes next action |
| **ReporterAgent** | Results Summarizer | Generates human-readable execution reports |

### 4.2 State Machine

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ INITIALIZING│────►│INVESTIGATING│────►│  PLANNING   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                       ┌───────────────────────┼─────────────┐
                       │                       │             │
                       ▼                       ▼             ▼
               ┌───────────────┐      ┌──────────────┐  ┌────────┐
               │  REPLANNING   │◄─────│  EXECUTING   │  │ FAILED │
               │  (loop back)  │      └──────┬───────┘  └────────┘
               └───────────────┘             │
                                              ▼
                                       ┌──────────────┐
                                       │  VERIFYING   │
                                       └──────┬───────┘
                                              │
                    ┌───────────────────────────┼───────────────────┐
                    │                           │                   │
                    ▼                           ▼                   ▼
            ┌──────────┐              ┌─────────────┐      ┌──────────┐
            │ CONTINUE │              │FAIL_REPLAN  │      │MAX_RETRIES│
            │(next step│              │(reinvestigate│      │ (skip)   │
            └────┬─────┘              └─────────────┘      └────┬─────┘
                 │                                               │
                 ▼                                               ▼
            ┌─────────┐                                     ┌──────────┐
            │ COMPLETE│                                     │  FAILED  │
            │         │                                     │          │
            └────┬────┘                                     └──────────┘
                 │
                 ▼
           ┌──────────┐
           │REPORTING │
           └──────────┘
```

### 4.3 Shared State Model

```python
class AgentState(BaseModel):
    # Core identifiers
    session_id: str                    # Unique execution session
    user_goal: str                     # Original user request
    
    # Execution tracking
    phase: AgentPhase                  # Current state in state machine
    plan: list[PlanStep]               # Ordered list of steps
    current_step_index: int            # Pointer to current step
    
    # Context and history
    environment_context: EnvironmentContext  # OS, shell, files, search results
    execution_history: list[dict]      # Log of all actions
    
    # Retry and circuit breaker
    retry_counts: dict[str, int]       # Per-step retry tracking
    max_retries_per_step: int = 999    # Configurable limit
    global_retry_count: int            # Total retries across all steps
    max_global_retries: int = 20       # Hard safety limit
    
    # Final result
    final_report: Optional[str]       # Generated by Reporter agent
    error_message: Optional[str]       # Fatal error description
```

### 4.4 Execution Flow

1. **Investigation Phase**
   - Agent analyzes user goal to determine required context
   - Generates read-only diagnostic commands
   - Performs web search for external knowledge
   - Performs RAG search for project context
   - Stores findings in `environment_context`

2. **Planning Phase**
   - Receives goal + environment context
   - Creates numbered steps with `logical_action` (plain English)
   - Each step has `id`, `description`, `logical_action`
   - No terminal syntax in plan (platform-agnostic)

3. **Execution Loop**
   ```
   For each step:
     a. Executor translates logical_action → OS-specific command
     b. Command executed via ShellRunner
     c. Verifier evaluates stdout/stderr/exit_code
     d. Verifier returns routing decision:
        - SUCCESS → next step
        - FAIL_RETRY → retry with fix
        - FAIL_REPLAN → back to Planner
        - FAIL_INVESTIGATE → re-investigate
        - MAX_RETRIES → skip step
   ```

4. **Verification Logic**
   - Success: exit_code == 0 AND no stderr errors
   - File creation: MUST verify content was written (not just file exists)
   - Failure classification:
     - `SYNTAX_ERROR` → route to Executor (fix command)
     - `ENVIRONMENT_ERROR` → route to Investigator (re-check)
     - `STRATEGY_ERROR` → route to Planner (rethink)
     - `EXECUTION_ERROR` → context-dependent

### 4.5 Failure Recovery System

```python
class FailureHint(str, Enum):
    MISSING_BINARY      = "missing_binary"      # Command not in PATH
    PERMISSION_DENIED   = "permission_denied"   # Need elevated privileges
    WRONG_CWD          = "wrong_cwd"           # Working directory incorrect
    MISSING_ENV_VAR    = "missing_env_var"    # Required env var not set
    INVALID_ARGUMENTS  = "invalid_arguments"  # Malformed arguments
    HOST_UNREACHABLE   = "host_unreachable"    # Network/SSH failure
    TIMEOUT            = "timeout"             # Command timed out
    MISSING_DEPENDENCY = "missing_dependency"  # Tool not installed
```

Executor applies **targeted fixes** based on failure hint:
- Missing binary → Try alternative commands, full paths
- Permission denied → Suggest elevated execution
- Wrong CWD → Adjust working directory
- Missing env var → Set required variables

---

## 5. Frontend Architecture (Webapp)

### 5.1 Project Structure

```
src/
├── app/
│   ├── page.tsx              # Main chat page (1058 lines)
│   ├── layout.tsx            # Root layout
│   ├── globals.css           # Global styles
│   ├── hooks/                # Custom React hooks
│   │   ├── useChat.ts        # Chat state management
│   │   ├── useStreaming.ts   # SSE streaming logic
│   │   ├── useTTS.ts         # Text-to-speech
│   │   ├── useBranching.ts   # Message tree navigation
│   │   ├── usePythonServer.ts # Python backend status
│   │   └── useKokoroServer.ts # TTS server status
│   └── api/                  # Next.js API routes
│       ├── terminal/route.ts      # Terminal proxy
│       ├── python/                # Python bridge routes
│       │   ├── terminal/route.ts
│       │   ├── multistep/route.ts
│       │   ├── ai/chat/route.ts
│       │   ├── settings/route.ts
│       │   └── agents/
│       │       ├── execute/route.ts
│       │       └── execute-stream/route.ts
│       └── kokoro/health/route.ts
├── components/
│   ├── chat-sidebar.tsx      # Chat session list
│   ├── agent-tracker.tsx     # Multi-agent progress UI
│   ├── settings-modal.tsx    # Configuration UI
│   ├── documentation.tsx     # Help panel
│   └── rename-modal.tsx      # Chat rename dialog
├── lib/
│   ├── api-client.ts         # OpenAI-compatible client
│   ├── chat-storage.ts       # localStorage persistence
│   ├── multistep.ts          # Plan execution types
│   ├── python-bridge.ts      # Python API client
│   └── utils.ts              # Utility functions
└── tools/
    ├── terminal/index.ts     # Terminal integration
    └── index.ts              # Tool exports
```

### 5.2 Key Components

#### ChatPage (`page.tsx`)
- **1058 lines** - Main orchestrator
- Manages: chat state, messages, streaming, TTS, terminal, settings, branching
- Uses **custom hooks** for feature separation
- Integrates with Python backend via `usePythonServer`

#### AgentTracker (`agent-tracker.tsx`)
- Visualizes multi-agent execution progress
- Shows: current phase, step progress, agent status
- Expandable to show detailed agent activity
- Icons: Search (Investigator), Clipboard (Planner), Terminal (Executor), CheckCircle (Verifier)

#### SettingsModal (`settings-modal.tsx`)
- Tabbed interface: Chat API, TTS, RAG, Behavior
- Settings persisted to `localStorage`
- Live Python backend status indicator

### 5.3 State Management

Uses **React hooks** with localStorage persistence:

```typescript
// Custom hooks pattern
const chat = useChat()           // Messages, sessions, history
const tts = useTTS()             // Audio playback state
const branching = useBranching()   // Message tree navigation
const ui = useUIState()          // Sidebar, modals, terminal panel
const pythonServer = usePythonServer()  // Backend connection
```

### 5.4 Streaming Architecture

```typescript
// SSE-based streaming from LLM
async function* streamChatCompletion(
  messages: ChatMessage[],
  enableTools: boolean
): AsyncGenerator<StreamChunk> {
  // 1. POST to /v1/chat/completions with stream=true
  // 2. Parse SSE chunks as they arrive
  // 3. Yield content deltas
  // 4. Parse tool calls from accumulated content
}
```

---

## 6. Backend Architecture (Python)

### 6.1 TUI Structure

```
src/tui/
├── tui.py              # Main Textual application (1286 lines)
├── api_server.py       # FastAPI server (1383 lines)
├── ai_client.py        # OpenAI client with streaming (649 lines)
├── multistep.py        # Plan execution engine (536 lines)
├── shell_runner.py     # Cross-platform shell execution
├── settings.py         # Configuration persistence (248 lines)
├── launcher.py         # OS detection and startup
├── rogius_agents.py    # Agent system integration
└── requirements.txt    # Python dependencies
```

### 6.2 FastAPI Server (`api_server.py`)

**Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Server status |
| `/terminal/execute` | POST | Execute shell command |
| `/multistep/create` | POST | Create new plan |
| `/multistep/execute` | POST | Execute next step |
| `/ai/chat` | POST | Streaming chat completion |
| `/settings` | GET/POST | Load/save settings |
| `/agents/execute` | POST | Run multi-agent workflow |
| `/agents/execute-stream` | POST | Streaming agent execution (SSE) |
| `/agents/sessions/{id}` | GET | Get session status |
| `/agents/prompts` | GET | Get agent system prompts |

### 6.3 ShellRunner

Cross-platform command execution:

```python
class ShellRunner:
    """Execute commands in platform-appropriate shell."""
    
    async def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30
    ) -> CommandResult:
        # Windows: PowerShell
        # Linux/macOS: Bash
        # Handles: quoting, escaping, timeouts
```

### 6.4 Multi-Step Plan Engine

```python
@dataclass
class Step:
    id: str
    description: str
    command: str
    status: StepStatus          # pending|running|completed|error|skipped
    result: Optional[str]       # stdout from execution
    error: Optional[str]        # stderr/exception
    dependencies: list[str]      # Step IDs that must complete first

class PlanManager:
    """Manages plan execution with dependencies."""
    
    async def execute_step(
        self,
        plan_id: str,
        step_index: int,
        shell_runner: ShellRunner
    ) -> StepResult:
        # Check dependencies
        # Execute command
        # Update status
        # Trigger dependent steps
```

---

## 7. RAG (Retrieval Augmented Generation)

### 7.1 Architecture

```
┌─────────────────────────────────────────────┐
│           PROJECT INDEXING                  │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐  │
│  │ File    │───►│ Chunk   │───►│ Embed   │  │
│  │ Crawler │    │ Text    │    │ (Local) │  │
│  └─────────┘    └─────────┘    └────┬────┘  │
│                                     │       │
│  ┌──────────────────────────────────▼────┐  │
│  │      Vector Store (Chroma/similar)   │  │
│  │  - Chunk embeddings                  │  │
│  │  - Metadata (file, line, content)    │  │
│  └──────────────────────────────────┬───┘  │
│                                     │       │
└─────────────────────────────────────┼───────┘
                                      │
┌─────────────────────────────────────▼───────┐
│           QUERY PROCESSING                  │
│  ┌─────────┐    ┌─────────┐    ┌────────┐ │
│  │ User    │───►│ Embed   │───►│ Search │ │
│  │ Query   │    │ Query   │    │ Vector │ │
│  └─────────┘    └─────────┘    └────┬───┘ │
│                                     │       │
│  ┌──────────────────────────────────▼────┐ │
│  │      Results (Top K chunks)          │ │
│  │  - Relevant code snippets            │ │
│  │  - File paths and line numbers       │ │
│  └──────────────────────────────────────┘ │
└───────────────────────────────────────────┘
```

### 7.2 Components

| File | Purpose |
|------|---------|
| `rag_indexer.py` | Background file indexing with watching |
| `rag_search.py` | Vector search with LlamaIndex/Chroma |
| `web_search.py` | External web search fallback |

### 7.3 Integration Points

- **Investigator Agent**: RAG search for project context
- **Planner Agent**: Uses results to understand existing code
- **Settings**: Configurable embedding model (default: nomic-embed-text)
- **Auto-indexing**: Enabled by default on startup

---

## 8. Tools & Integrations

### 8.1 Available Tools

| Tool | Description | Implemented In |
|------|-------------|----------------|
| `execute_command` | Run shell command | `shell_runner.py`, `useTerminal.ts` |
| `open_terminal` | Show terminal panel | UI state management |
| `start_multistep_task` | Create execution plan | `multistep.py`, `PlanManager` |
| `execute_next_step` | Run next plan step | `multistep.py` |
| `modify_step` | Edit a step | `multistep.py` |
| `skip_step` | Skip a step | `multistep.py` |
| `add_step` | Add new step | `multistep.py` |
| `verify_task_completion` | Check if done | `multistep.py` |
| `web_search` | Search internet | `web_search.py` |
| `rag_search` | Search project | `rag_search.py` |

### 8.2 TTS Integration

- **Provider**: Kokoro TTS (runs on remote Linux machine via SSH)
- **Endpoint**: `http://100.71.89.62:8880/v1/audio/speech`
- **Voices**: American/British male/female (af_bella, am_echo, etc.)
- **Webapp**: Full support with auto-play option
- **TUI**: Not implemented

---

## 9. Configuration System

### 9.1 Webapp (localStorage)

```typescript
interface APIConfig {
  chatEndpoint: string        // http://localhost:1234/v1/chat/completions
  chatApiKey: string          // Optional
  chatModel: string           // e.g., "qwen_qwen3.5-27b"
  chatContextLength: number   // 262144
  ttsEndpoint: string         // http://100.71.89.62:8880/v1/audio/speech
  ttsVoice: string            // "af_bella"
  autoPlayAudio: boolean      // false
  maxRetries: number          // 999
}
```

### 9.2 TUI (JSON File)

```python
# Windows: %APPDATA%/Rogius/settings.json
# Linux/macOS: ~/.config/rogius/settings.json

@dataclass
class TUISettings:
    chat_endpoint: str = "http://localhost:1234/v1/chat/completions"
    chat_model: str = "llama-3.1-8b"
    max_retries: int = 999
    rag_enabled: bool = True
    rag_embedding_model: str = "nomic-embed-text"
```

### 9.3 Project Config (`rogius.config.json`)

```json
{
  "chatEndpoint": "http://100.71.89.62:1234/v1/chat/completions",
  "chatModel": "qwen_qwen3.5-27b",
  "chatContextLength": 262144,
  "ttsEndpoint": "http://100.71.89.62:8880/v1/audio/speech",
  "ttsVoice": "af_bella"
}
```

---

## 10. Data Flow Examples

### 10.1 Simple Command Execution

```
User: "Create a file called hello.txt with 'Hello World'"
  │
  ▼
┌─────────────────────────────────────────┐
│ LLM receives message with system prompt │
│ containing shell instructions           │
└─────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────┐
│ LLM generates tool call:               │
│ {                                      │
│   "name": "execute_command",           │
│   "arguments": {                       │
│     "command": "New-Item -Path ..."    │
│   }                                    │
│ }                                      │
└─────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────┐
│ Webapp/TUI extracts tool call          │
│ and routes to shell_runner             │
└─────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────┐
│ Command executed in PowerShell/Bash    │
│ Result returned to UI                  │
└─────────────────────────────────────────┘
```

### 10.2 Multi-Agent Task Execution

```
User: "Set up a Python virtual environment and install requests"
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ POST /agents/execute-stream                         │
│ { "goal": "Set up venv and install requests" }       │
└─────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ 1. INVESTIGATOR                                     │
│    - Detects OS: Windows                            │
│    - Detects Shell: PowerShell                       │
│    - Checks: Python installed? pip available?        │
└─────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ 2. PLANNER                                          │
│    Creates steps:                                   │
│    1. Create venv: python -m venv .venv             │
│    2. Activate: .venv\Scripts\Activate.ps1           │
│    3. Install: pip install requests                  │
└─────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ 3. EXECUTOR + VERIFIER (Loop)                       │
│    Step 1: Execute → Verify → Success              │
│    Step 2: Execute → Verify → Success                │
│    Step 3: Execute → Verify → Success                │
└─────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────┐
│ 4. REPORTER                                         │
│    Generates: "Successfully created venv and       │
│    installed requests. Activation command: ..."      │
└─────────────────────────────────────────────────────┘
  │
  ▼
SSE Events → Frontend → AgentTracker updates
```

---

## 11. Current State & Known Issues

### 11.1 Feature Parity (Webapp vs TUI)

| Feature | Webapp | TUI | Status |
|---------|--------|-----|--------|
| Chat streaming | ✅ | ✅ | Parity |
| Tool calling | ✅ | ✅ | Parity |
| Multi-step execution | ✅ | ✅ | Parity |
| Terminal integration | ✅ | ✅ | Parity |
| Settings persistence | ✅ | ✅ | Parity |
| Chat sessions/sidebar | ✅ | ❌ | TUI gap |
| Message branching | ✅ | ❌ | TUI gap |
| TTS playback | ✅ | ❌ | TUI gap |
| RAG search | ✅ | ✅ | Parity |

### 11.2 Architecture Issues (Documented)

From `src/Notes_for_LLMS/architecture_issues/`:

1. **God File Anti-Pattern**: `page.tsx` (1058 lines) contains 20+ concerns
2. **Dual Terminal Execution**: Two parallel terminal systems exist
3. **Mixed Data Flow**: Streaming logic scattered across components
4. **Spaghetti Tool Execution**: Tool handling in multiple places
5. **Type Fragmentation**: Multiple similar type definitions
6. **Debug Code Pollution**: Console logs throughout codebase

### 11.3 Build Configuration

```javascript
// next.config.js
const nextConfig = {
  output: 'export',      // Static export
  distDir: 'dist',
  images: {
    unoptimized: true,  // Required for static export
  },
}
```

**Scripts:**
- `npm run dev` - Development server
- `npm run build` - Static export to `dist/`
- `npm run python-api:start` - Start Python backend
- `npm run dev:full` - Start both Python API and Next.js

---

## 12. API Reference

### 12.1 Python Backend API

#### Execute Multi-Agent Workflow
```http
POST /agents/execute-stream
Content-Type: application/json

{
  "goal": "Create a Python script that fetches weather data",
  "session_id": "optional-custom-id"
}

Response: text/event-stream

data: {"type": "phase", "phase": "investigation", "message": "Probing environment..."}

data: {"type": "start", "goal": "...", "total_steps": 5}

data: {"type": "step_start", "step": 0, "description": "Check Python installation"}

data: {"type": "step_complete", "step": 0, "result": "Python 3.11 found", "output": "..."}

data: {"type": "agent_prompt", "agent": "Investigator", "system_prompt": "...", "user_prompt": "..."}

data: {"type": "agent_inference", "agent": "Investigator", "response": "..."}

data: {"type": "complete", "status": "complete", "completed": 5, "total": 5, "percentage": 100}

data: {"type": "report", "report": "Successfully created weather script..."}
```

#### Execute Terminal Command
```http
POST /terminal/execute
Content-Type: application/json

{
  "command": "Get-ChildItem -Path . -Name",
  "cwd": "optional/working/directory",
  "timeout": 30
}

Response:
{
  "stdout": "file1.txt\nfile2.py",
  "stderr": "",
  "exit_code": 0,
  "command": "Get-ChildItem..."
}
```

### 12.2 Agent System Prompts

Available at `GET /agents/prompts`:
- `investigator` - Environment probing instructions
- `planner` - Plan creation guidelines
- `executor` - Command translation rules
- `verifier` - Success/failure evaluation
- `rogius_main` - Orchestrator instructions

---

## 13. Development Guide

### 13.1 Adding a New Tool

1. **Define tool schema** in `ai_client.py` (`TERMINAL_TOOLS`)
2. **Implement handler** in `api_server.py` or `tui.py`
3. **Update system prompt** to mention new capability
4. **Add UI support** if needed (webapp components)

### 13.2 Adding a New Agent

1. **Create agent file** in `src/subagents/{new_agent}.py`
2. **Inherit from base** or follow existing pattern
3. **Add to `__init__.py`** exports
4. **Integrate in `RogiusMainAgent`** workflow
5. **Add system prompt** to `prompts.py`
6. **Update UI** to show new agent status

### 13.3 Testing

```bash
# Test TUI components
python -m pytest src/tui/test_*.py

# Test subagents
python src/subagents/test_integration.py

# Run TUI directly
python src/tui/tui.py

# Start Python API server
python src/tui/api_server.py
```

---

## 14. Deployment

### 14.1 Webapp (Static)

```bash
# Build static export
npm run build

# Deploy dist/ folder to:
# - Netlify
# - Vercel
# - GitHub Pages
# - Any static host
```

### 14.2 Python Backend

```bash
# Install dependencies
pip install -r src/tui/requirements.txt

# Run server
python src/tui/api_server.py
# or
uvicorn src.tui.api_server:app --host 0.0.0.0 --port 8000
```

### 14.3 Environment Variables

```bash
# Optional: Change Python API URL
NEXT_PUBLIC_PYTHON_API_URL=http://127.0.0.1:8000
PYTHON_API_URL=http://127.0.0.1:8000
```

---

## 15. Future Roadmap

From `src/Notes_for_LLMS/Roadmap/`:

1. **File Editor Operations** - Better file modification tools
2. **Code Search Analysis** - Enhanced RAG with code understanding
3. **Web External Integration** - Browser automation
4. **Browser Preview** - Live preview for web projects
5. **Deployment Tools** - Automated deployment
6. **Memory/Context Management** - Long-term memory
7. **Task Management** - Project-level task tracking
8. **Command Execution Improvements** - Better error handling

---

## 16. Conclusion

Rogius represents a **production-ready multi-agent system** with:
- **Sophisticated orchestration** via 6 specialized agents
- **Self-healing execution** with retry loops and replanning
- **Dual interface** (web + terminal) for flexibility
- **Local-first architecture** for privacy and control
- **Extensible tool system** for custom integrations

The codebase demonstrates modern patterns for AI-powered automation while maintaining clear separation of concerns and comprehensive error handling.

---

**Document Authors:** Cascade (AI Assistant)  
**Review Status:** Ready for Engineering Review  
**Last Updated:** April 23, 2026
