# Rogius

A multi-agent AI system with self-healing execution and a decoupled tool-based architecture.

## Overview

Rogius is an autonomous AI agent system that can execute complex tasks through a pipeline of specialized agents. The system features self-healing execution, automatic retry logic, and a flexible tool registry that enables easy extension with new capabilities.

## Architecture

### Multi-Agent Pipeline

Rogius uses a sequential agent pipeline:

1. **Investigator** - Gathers environment context (OS, shell, available commands, files)
2. **Planner** - Creates a step-by-step execution plan
3. **Executor** - Generates structured Actions for tools to execute
4. **Verifier** - Evaluates execution results and determines next actions
5. **Reporter** - Summarizes results for the user
6. **RogiusMainAgent** - Orchestrates the entire workflow

### Tool-Based Architecture

The system uses a decoupled tool architecture where:

- **Executor** generates `Action` objects (not raw commands)
- **ToolRegistry** dispatches Actions to appropriate tools
- **Tools** handle execution and provide verification helpers
- **Verifier** evaluates ToolResults and routes the workflow

This design enables easy addition of new tools without modifying the agents.

## Available Tools

### TerminalTool

Executes shell commands across platforms (PowerShell on Windows, Bash on Linux/macOS).

**Action Type:** `terminal_command`

**Features:**
- Cross-platform command execution
- Failure classification and automatic fix application
- File creation verification
- Permission handling

**Example:**
```python
{
    "type": "terminal_command",
    "payload": {
        "command": "New-Item -Path 'file.txt' -ItemType File -Value 'Hello World'",
        "cwd": "optional working directory"
    },
    "description": "Create a file with content",
    "timeout": 30
}
```

### BrowserTool

Web automation using Playwright with DOM-based interaction (not OCR).

**Action Type:** `web_crawl`

**Features:**
- Headed mode by default (visible browser)
- Screenshot capture after every operation
- Persistent sessions across multiple actions
- Automatic screenshot cleanup
- Supports Chromium, Firefox, WebKit

**Operations:**
- `goto` - Navigate to URL
- `click` - Click element by selector
- `fill` - Fill input field
- `type` - Type with keystroke delay
- `select` - Select dropdown option
- `wait` - Wait for element to appear
- `extract` - Extract text/attributes from elements
- `scroll` - Scroll page
- `screenshot` - Capture screenshot
- `close` - Close browser session

**Example:**
```python
{
    "type": "web_crawl",
    "payload": {
        "url": "https://example.com",
        "operations": [
            {"type": "fill", "selector": "#search", "value": "python"},
            {"type": "click", "selector": "#submit"},
            {"type": "wait", "selector": ".results"},
            {"type": "extract", "selector": ".result-title", "as": "titles", "limit": 5},
            {"type": "close"}
        ],
        "headless": false,
        "slow_mo": 500
    },
    "description": "Search and extract results",
    "timeout": 60
}
```

## Installation

### Prerequisites

- Python 3.11+
- Virtual environment (recommended)

### Setup

```bash
# Clone the repository
git clone https://github.com/rgoza1996/Rogius.git
cd Rogius

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for BrowserTool)
playwright install chromium
```

## Usage

### Running the Webapp

```bash
# Start Python backend
python src/tui/api_server.py

# Start Next.js frontend (in another terminal)
cd src/webapp
npm install
npm run dev
```

### Running the TUI

```bash
python src/tui/tui.py
```

### API Usage

The Python backend exposes a FastAPI server on port 8000 by default.

**Multi-agent execution endpoint:**
```
POST /api/agents/execute-stream
```

## Configuration

Configuration is managed via `rogius.config.json`:

```json
{
  "chat_endpoint": "https://api.openai.com/v1/chat/completions",
  "chat_model": "gpt-4",
  "tts_endpoint": "http://100.71.89.62:8880/v1/audio/speech",
  "rag_enabled": true
}
```

## Development

### Adding a New Tool

1. Create a new file in `src/tools/` (e.g., `my_tool.py`)
2. Implement the `Tool` interface:
   ```python
   from .tool_interface import Tool, Action, ActionType, ToolResult
   from .tool_registry import tool

   @tool(ActionType.MY_ACTION)
   class MyTool(Tool):
       @property
       def action_type(self) -> ActionType:
           return ActionType.MY_ACTION

       async def execute(self, action: Action, env_context: dict) -> ToolResult:
           # Implementation
           pass
   ```
3. Add the action type to `tool_interface.py`
4. Import the tool in `tools/__init__.py` (triggers auto-registration)
5. Update `prompts.py` with the new action schema

### Project Structure

```
Rogius/
├── src/
│   ├── subagents/          # Agent implementations
│   │   ├── executor.py
│   │   ├── verifier.py
│   │   ├── planner.py
│   │   ├── investigator.py
│   │   ├── reporter.py
│   │   └── main.py
│   ├── tools/              # Tool implementations
│   │   ├── tool_interface.py
│   │   ├── tool_registry.py
│   │   ├── terminal_tool.py
│   │   ├── browser_tool.py
│   │   └── __init__.py
│   ├── tui/                # Terminal UI
│   ├── app/                # Next.js webapp
│   └── lib/                # Shared utilities
├── scripts/                # Utility scripts
└── rogius.config.json      # Configuration
```

## Features

- **Self-Healing Execution**: Automatic retry with targeted fixes based on failure classification
- **Circuit Breaker**: Prevents infinite retry loops
- **Streaming**: Real-time progress updates via Server-Sent Events
- **RAG Integration**: Local codebase indexing for context
- **TTS Support**: Text-to-speech for voice feedback
- **Dual Interface**: Webapp (Next.js) and Terminal UI (Python Textual)

## License

MIT License

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
