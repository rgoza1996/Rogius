# Changelog

All notable changes to Rogius will be documented in this file.

## [Unreleased]

### Added

#### New Tools (Phase 1 - Core Local AI Workflow)

- **FileEditTool** (`src/tools/file_edit_tool.py`)
  - Structured file editing operations (create, read, replace, insert, delete, append)
  - Multi-operation atomic transactions
  - Regex and exact text matching for replacements
  - File creation verification
  - Automatic failure recovery (create file if missing, enable overwrite)
  - Designed for precise file manipulation in local AI workflows

- **GitTool** (`src/tools/git_tool.py`)
  - Version control operations with safety checks
  - Readonly operations: status, log, diff, show, branch, remote
  - Modifying operations require `confirmed: true` flag
  - Parsed output (status, log commits, diff files, branches)
  - Failure classification: not_a_repo, permission_denied, merge_conflict, etc.
  - Safe defaults prevent accidental destructive operations

- **SearchTool** (`src/tools/search_tool.py`)
  - Fast code search using ripgrep (with grep/Python fallbacks)
  - Text and regex pattern matching
  - File type and pattern filtering
  - Context lines around matches
  - Structured results with file paths, line numbers, match positions
  - Optimized for local codebase exploration

- **ModelManagementTool** (`src/tools/model_management_tool.py`)
  - Switch between local AI models and external APIs
  - Operations: status, list, switch, test, configure
  - Auto-detect provider type (LM Studio, Ollama, OpenAI, Anthropic, Groq)
  - Test endpoint connectivity before switching
  - Support for local-first with external fallback
  - Configuration persistence in `rogius.config.json`

#### Updated Prompts
- **Planner Prompt** (`src/subagents/prompts.py`)
  - Added action type selection guide for new tools
  - Documented when to use file_edit vs terminal_command
  - Documented when to use git_command vs terminal_command

- **Executor Prompt** (`src/subagents/prompts.py`)
  - Added complete schemas for all 6 action types
  - Included examples for file_edit, git_command, code_search, model_manage
  - Added rules for tool selection (prefer specific tools over generic terminal)

#### Tool-Based Architecture Refactoring
- **Tool Interface** (`src/tools/tool_interface.py`)
  - Base `Tool` class with `execute()`, `verify()`, and `apply_failure_fix()` methods
  - `Action` model for structured action representation
  - `ToolResult` model for tool-agnostic execution results
  - `ActionType` enum for action type registration

- **Tool Registry** (`src/tools/tool_registry.py`)
  - Self-registering tool system using `@tool` decorator
  - Central dispatcher for action execution
  - Automatic tool registration on import

- **TerminalTool** (`src/tools/terminal_tool.py`)
  - Encapsulates all shell execution logic
  - Cross-platform support (PowerShell/Bash)
  - Failure classification and automatic fix application
  - File creation verification
  - Moved from Executor/Verifier agents to dedicated tool

- **BrowserTool** (`src/tools/browser_tool.py`)
  - Web automation using Playwright
  - DOM-based interaction (not OCR)
  - Headed mode by default (visible browser)
  - Screenshot capture after every operation
  - Automatic screenshot cleanup (keeps last 50)
  - Persistent sessions across multiple actions
  - Supports Chromium, Firefox, WebKit
  - Operations: goto, click, fill, type, select, wait, extract, scroll, hover, press, evaluate, screenshot, close

#### Updated Models
- Added `ActionType` enum to `models.py`
- Added `Action` model to `models.py`
- Updated `PlanStep` to include `action` field (backward compatible with `command`)

#### Updated Agents
- **Executor Agent** (`src/subagents/executor.py`)
  - Now generates `Action` objects instead of raw terminal commands
  - Uses `ToolRegistry.execute()` for action dispatch
  - Returns `Action` and `ToolResult` instead of `CommandResult`

- **Verifier Agent** (`src/subagents/verifier.py`)
  - Now accepts `Action` and `ToolResult` instead of `CommandResult`
  - Delegates verification to tool-specific `verify()` methods
  - Updated failure classification for web_crawl actions

- **Main Agent** (`src/subagents/main.py`)
  - Updated to import tools for auto-registration
  - Updated Executor/Verifier calls with new signatures

#### Updated Prompts
- **Executor Prompt** (`src/subagents/prompts.py`)
  - Updated to generate `Action` objects with type and payload
  - Added comprehensive web_crawl schema and examples
  - Added selector strategy guidelines
  - Added operation type documentation

- **Verifier Prompt** (`src/subagents/prompts.py`)
  - Updated to handle `ToolResult` artifacts
  - Added web_crawl-specific failure hints
  - Added web_crawl verification guidance

### Changed

- **Architecture**: Decoupled terminal logic from agents using tool pattern
- **Execution Flow**: Executor → Action → ToolRegistry → Tool → ToolResult → Verifier
- **Failure Handling**: Tools now provide their own failure classification and fix application
- **Extensibility**: New tools can be added without modifying agents

### Fixed

- Removed tight coupling between Executor and terminal commands
- Removed tight coupling between Verifier and CommandResult
- Improved failure classification with tool-specific logic

## [0.1.0] - Initial Release

### Added
- Multi-agent system (Investigator, Planner, Executor, Verifier, Reporter)
- Self-healing execution with retry logic
- Terminal command execution
- RAG integration for codebase context
- TTS support for voice feedback
- Dual interface (Webapp + TUI)
- Streaming progress updates via SSE
