# Prompt: Implement Command Execution Improvements

## Goal
Enhance Rogius's command execution capabilities with better async handling, status checking, and terminal output streaming to match Windsurf's robust terminal integration.

## Tools to Implement

### 1. `run_command`
**Purpose**: Execute commands with proper async/blocking semantics and safety controls
**Parameters**:
- `CommandLine` (string, required): Exact command string to execute
- `Cwd` (string, optional): Working directory for the command
- `Blocking` (boolean, optional): 
  - `true`: Block until command completes (for short operations)
  - `false`: Run async for long-running processes (servers, etc.)
- `SafeToAutoRun` (boolean, optional): 
  - `true`: Safe to run without user approval
  - `false`: Requires user approval (destructive operations)
- `WaitMsBeforeAsync` (number, optional): Milliseconds to wait for quick errors before going fully async

**CRITICAL RULES**:
- **NEVER** include `cd` in CommandLine - use `Cwd` parameter instead
- Set `SafeToAutoRun=false` for any destructive side-effects (deleting files, mutating state, installing dependencies, external requests)
- Set `SafeToAutoRun=true` ONLY if extremely confident it's safe
- Cannot auto-run potentially unsafe commands even if user asks

**Safety Categories**:
```
SAFE (can auto-run):
- Reading files (cat, head, less)
- Listing directories (ls, dir)
- Checking status (git status, system info)
- Simple prints (echo)

UNSAFE (requires approval):
- File deletion (rm, del)
- Writing files (> file.txt)
- Installing packages (npm install, pip install)
- Network requests (curl, wget)
- Git operations (git push, git reset)
- Running unknown scripts
```

### 2. `command_status`
**Purpose**: Check status of a previously started background command
**Parameters**:
- `CommandId` (string, required): ID of the command to check
- `OutputCharacterCount` (number, required): Number of characters to return (keep small to avoid memory issues)
- `WaitDurationSeconds` (number, optional): Seconds to wait for completion before returning status

**Features**:
- Returns current status (running or done)
- Returns output lines as specified by priority
- Returns any error if present
- Can wait up to specified duration for completion

### 3. `read_terminal`
**Purpose**: Read contents of a terminal by its process ID
**Parameters**:
- `Name` (string, required): Terminal name identifier
- `ProcessID` (string, required): Process ID of the terminal

**Features**:
- Read terminal output streams
- Access to specific terminal by name and PID

## Implementation Notes

### For Webapp:

```typescript
// Enhanced terminal state in src/tools/terminal/store.ts

interface EnhancedTerminalCommand extends TerminalCommand {
  commandId: string;  // Unique ID for async tracking
  blocking: boolean;
  safeToAutoRun: boolean;
  outputBuffer: string;
  maxOutputSize: number;
}

interface CommandExecutionManager {
  // Track running commands
  activeCommands: Map<string, EnhancedTerminalCommand>;
  
  // Execute with safety check
  async execute(command: string, options: {
    cwd?: string;
    blocking?: boolean;
    safeToAutoRun?: boolean;
    waitMs?: number;
  }): Promise<CommandResult>;
  
  // Check status
  async getStatus(commandId: string, outputLimit: number): Promise<CommandStatus>;
  
  // Stream output
  onOutput(commandId: string, callback: (output: string) => void): void;
}

// API endpoints:
// POST /api/terminal/execute - Start command
// GET /api/terminal/status/:id - Check status
// WebSocket /api/terminal/stream - Real-time output
```

```typescript
// Safety check implementation
const UNSAFE_PATTERNS = [
  /\brm\s+-[rf]*\b/i,  // rm -rf
  /\bdel\s+\/f/i,       // del /f
  /\bmkfs\b/i,         // mkfs
  /\bdd\s+if=/i,       // dd
  /\bcurl\s+.*\|\s*(bash|sh)/i,  // curl | bash
  /\bwget\s+.*\|\s*(bash|sh)/i,  // wget | bash
  /\bformat\b/i,       // format
  /\b>\s*\//i,         // overwrite system files
];

function isUnsafeCommand(command: string): boolean {
  return UNSAFE_PATTERNS.some(pattern => pattern.test(command));
}

function requiresApproval(command: string): boolean {
  // Check against security levels
  const securityLevel = getSecurityLevel();
  
  if (securityLevel === 'always-confirm') return true;
  if (isUnsafeCommand(command)) return true;
  
  // Check command categories
  const destructiveCommands = ['rm', 'del', 'rmdir', 'format', 'mkfs'];
  const installCommands = ['npm install', 'pip install', 'apt', 'yum'];
  const gitDestructive = ['git push', 'git reset', 'git clean'];
  
  return destructiveCommands.some(cmd => command.includes(cmd)) ||
         installCommands.some(cmd => command.includes(cmd)) ||
         gitDestructive.some(cmd => command.includes(cmd));
}
```

### For TUI:

```python
# Add to src/tui/ai_client.py
# Implement in src/tui/command_runner.py

import asyncio
import subprocess
import uuid
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum

class CommandStatus(Enum):
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"
    CANCELLED = "cancelled"

@dataclass
class RunningCommand:
    command_id: str
    process: subprocess.Popen
    command_line: str
    cwd: Optional[str]
    status: CommandStatus
    stdout_buffer: list[str]
    stderr_buffer: list[str]
    callbacks: list[Callable]

class AsyncCommandRunner:
    def __init__(self):
        self.active_commands: dict[str, RunningCommand] = {}
        self._output_queues: dict[str, asyncio.Queue] = {}
    
    async def run_command(
        self,
        command_line: str,
        cwd: Optional[str] = None,
        blocking: bool = False,
        safe_to_auto_run: bool = False,
        wait_ms_before_async: int = 0
    ) -> str:  # Returns command_id
        # Validate safety
        if not safe_to_auto_run and self._requires_approval(command_line):
            approved = await self._request_approval(command_line)
            if not approved:
                raise PermissionError("Command not approved by user")
        
        # Generate unique ID
        command_id = str(uuid.uuid4())[:8]
        
        # Start process
        process = await asyncio.create_subprocess_shell(
            command_line,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=1024 * 1024  # 1MB buffer
        )
        
        running_cmd = RunningCommand(
            command_id=command_id,
            process=process,
            command_line=command_line,
            cwd=cwd,
            status=CommandStatus.RUNNING,
            stdout_buffer=[],
            stderr_buffer=[],
            callbacks=[]
        )
        
        self.active_commands[command_id] = running_cmd
        self._output_queues[command_id] = asyncio.Queue()
        
        # Start output streaming
        asyncio.create_task(self._stream_output(running_cmd))
        
        if blocking:
            await process.wait()
            running_cmd.status = CommandStatus.DONE
            return command_id
        
        # Wait briefly for quick errors
        if wait_ms_before_async > 0:
            try:
                await asyncio.wait_for(process.wait(), timeout=wait_ms_before_async / 1000)
                running_cmd.status = CommandStatus.DONE
            except asyncio.TimeoutError:
                pass  # Continue running async
        
        return command_id
    
    async def get_status(
        self,
        command_id: str,
        output_character_count: int,
        wait_duration_seconds: int = 0
    ) -> dict:
        cmd = self.active_commands.get(command_id)
        if not cmd:
            return {"error": "Command not found"}
        
        if wait_duration_seconds > 0 and cmd.status == CommandStatus.RUNNING:
            try:
                await asyncio.wait_for(
                    cmd.process.wait(),
                    timeout=wait_duration_seconds
                )
                cmd.status = CommandStatus.DONE
            except asyncio.TimeoutError:
                pass
        
        # Collect output
        stdout = ''.join(cmd.stdout_buffer)[-output_character_count:]
        stderr = ''.join(cmd.stderr_buffer)[-output_character_count:]
        
        return {
            "status": cmd.status.value,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": cmd.process.returncode if cmd.process.returncode is not None else None
        }
    
    async def _stream_output(self, cmd: RunningCommand):
        """Stream stdout/stderr to buffers and callbacks"""
        while True:
            stdout_line = await cmd.process.stdout.readline()
            if stdout_line:
                line = stdout_line.decode().rstrip()
                cmd.stdout_buffer.append(line + '\n')
                for callback in cmd.callbacks:
                    callback('stdout', line)
            
            stderr_line = await cmd.process.stderr.readline()
            if stderr_line:
                line = stderr_line.decode().rstrip()
                cmd.stderr_buffer.append(line + '\n')
                for callback in cmd.callbacks:
                    callback('stderr', line)
            
            if cmd.process.stdout.at_eof() and cmd.process.stderr.at_eof():
                break
        
        await cmd.process.wait()
        cmd.status = CommandStatus.DONE
    
    def _requires_approval(self, command: str) -> bool:
        # Same safety checks as webapp
        unsafe_patterns = [
            r'\brm\s+-[rf]*\b',
            r'\bdel\s+/f',
            r'\bmikfs\b',
            r'\bdd\s+if=',
            r'\bcurl\s+.*\|\s*(bash|sh)',
            r'\bwget\s+.*\|\s*(bash|sh)',
        ]
        import re
        return any(re.search(pattern, command, re.I) for pattern in unsafe_patterns)
    
    async def _request_approval(self, command: str) -> bool:
        # Show prompt in TUI
        # Return True if user approves
        pass
```

### Tool Definitions:

```typescript
// Add to TERMINAL_TOOLS in src/lib/api-client.ts
const EXECUTION_TOOLS = [
  {
    type: 'function',
    function: {
      name: 'run_command',
      description: 'Execute a command on behalf of the user. Operating System specific (Windows: PowerShell, Linux/Mac: bash). NEVER include "cd" in CommandLine - use Cwd parameter instead. Set SafeToAutoRun=false for destructive side-effects (deleting files, mutating state, installing dependencies). Set Blocking=true only if command will terminate quickly.',
      parameters: {
        type: 'object',
        properties: {
          CommandLine: { 
            type: 'string', 
            description: 'Exact command line to execute' 
          },
          Cwd: { 
            type: 'string', 
            description: 'Working directory for the command' 
          },
          Blocking: { 
            type: 'boolean', 
            description: 'Block until command finishes. Only true for short commands.' 
          },
          SafeToAutoRun: { 
            type: 'boolean', 
            description: 'Safe to run without approval. Set to false for destructive operations.' 
          },
          WaitMsBeforeAsync: { 
            type: 'number', 
            description: 'Milliseconds to wait for quick errors before going async' 
          }
        },
        required: ['CommandLine']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'command_status',
      description: 'Check the status of a background command by its ID. Returns current status, output lines, and any errors. Only use for IDs returned by run_command.',
      parameters: {
        type: 'object',
        properties: {
          CommandId: { 
            type: 'string', 
            description: 'ID of the command to check' 
          },
          OutputCharacterCount: { 
            type: 'number', 
            description: 'Number of characters to return (keep small)' 
          },
          WaitDurationSeconds: { 
            type: 'number', 
            description: 'Seconds to wait for completion before returning' 
          }
        },
        required: ['CommandId', 'OutputCharacterCount']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'read_terminal',
      description: 'Read the contents of a terminal by its process ID and name.',
      parameters: {
        type: 'object',
        properties: {
          Name: { type: 'string', description: 'Terminal name' },
          ProcessID: { type: 'string', description: 'Process ID of the terminal' }
        },
        required: ['Name', 'ProcessID']
      }
    }
  }
];
```

## Enhanced Security Model:

```typescript
// Security levels
enum SecurityLevel {
  AUTO = 'auto',                    // AI decides based on heuristics
  CONFIRM_DESTRUCTIVE = 'confirm-destructive',  // Confirm rm, git push, etc.
  ALWAYS_CONFIRM = 'always-confirm' // Confirm all commands
}

interface SecurityResult {
  allowed: boolean;
  level: SecurityLevel;
  reason?: string;
  requiresConfirmation: boolean;
}

function checkSecurity(command: string, level: SecurityLevel): SecurityResult {
  const categories = categorizeCommand(command);
  
  if (level === SecurityLevel.ALWAYS_CONFIRM) {
    return { allowed: true, level, requiresConfirmation: true };
  }
  
  if (level === SecurityLevel.CONFIRM_DESTRUCTIVE && 
      (categories.destructive || categories.network || categories.gitDestructive)) {
    return { allowed: true, level, requiresConfirmation: true };
  }
  
  if (categories.critical) {
    return { allowed: false, level, reason: 'Critical system command blocked', requiresConfirmation: false };
  }
  
  return { allowed: true, level, requiresConfirmation: false };
}
```

## Use Cases:

### Safe Command:
```
AI: run_command({
  CommandLine: "ls -la",
  Cwd: "/home/user/project",
  Blocking: true,
  SafeToAutoRun: true
})
```

### Destructive Command:
```
AI: run_command({
  CommandLine: "rm -rf node_modules",
  Blocking: false,
  SafeToAutoRun: false  // Will prompt for approval
})
```

### Long-Running Server:
```
AI: run_command({
  CommandLine: "npm run dev",
  Cwd: "/home/user/project",
  Blocking: false,
  SafeToAutoRun: true,
  WaitMsBeforeAsync: 3000  // Wait 3s for startup errors
})
// Returns command_id for status checks

// Later...
AI: command_status({
  CommandId: "cmd-abc-123",
  OutputCharacterCount: 5000,
  WaitDurationSeconds: 0
})
```

## Testing Checklist
- [ ] Blocking command execution
- [ ] Non-blocking async execution
- [ ] Safety approval prompt
- [ ] Auto-run safe commands
- [ ] Block critical commands
- [ ] Cwd parameter (no cd in command)
- [ ] Command status checking
- [ ] Output streaming
- [ ] Output character limiting
- [ ] Wait duration for completion
- [ ] Error handling
- [ ] Command cleanup on exit
- [ ] Windows PowerShell support
- [ ] Unix bash support
- [ ] Terminal output reading
