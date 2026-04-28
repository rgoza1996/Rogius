"""
AI Client for Rogius TUI

OpenAI-compatible API client with streaming and tool calling support.
Matches the webapp's api-client.ts functionality.
"""

import json
import asyncio
import aiohttp
from typing import Optional, AsyncGenerator, Callable, Awaitable, Any
from dataclasses import dataclass
from enum import Enum

# Import web search for built-in tool handler
try:
    from tools.web_search import web_search
except ImportError:
    # Fallback for when running from tui folder directly
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tools.web_search import web_search


class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ToolCall:
    id: Optional[str]
    index: int
    type: str
    function_name: Optional[str]
    function_arguments: str
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "index": self.index,
            "type": self.type,
            "function": {
                "name": self.function_name,
                "arguments": self.function_arguments
            }
        }


@dataclass
class StreamChunk:
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    finish_reason: Optional[str] = None


@dataclass
class APIConfig:
    chat_endpoint: str = "http://localhost:1234/v1/chat/completions"
    chat_api_key: str = ""
    chat_model: str = "llama-3.1-8b"
    chat_context_length: int = 4096
    tts_endpoint: str = "http://100.71.89.62:8880/v1/audio/speech"
    tts_api_key: str = ""
    tts_voice: str = "af_bella"
    system_prompt: str = ""
    auto_play_audio: bool = False


# Tool definitions matching the webapp
TERMINAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a PowerShell command on the Windows machine. TRIGGER: Use this tool IMMEDIATELY for ANY request involving: random numbers, math calculations, file operations, opening apps, running scripts, system info, date/time, process management, or ANY task requiring computation. DO NOT explain you cannot do it - JUST USE THIS TOOL. Examples: 'random number' → use this tool with Get-Random; 'what time is it' → use this tool with Get-Date; 'create a file' → use this tool with New-Item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute (e.g., 'notepad', 'code .', 'ls', 'dir', 'mkdir folder')"
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Optional working directory (relative to project root)"
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_terminal",
            "description": "Open the terminal panel UI so the user can see terminal output.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_multistep_task",
            "description": "Start a multi-step task with a goal and planned steps. CRITICAL: Use this automatically for ANY task that involves multiple actions, sequential operations, or the words 'and', 'then', 'afterwards', 'verify'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "Clear description of the overall task goal"},
                    "steps": {
                        "type": "array",
                        "description": "List of steps to execute in order",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string", "description": "What this step does"},
                                "command": {"type": "string", "description": "Shell command to execute"}
                            },
                            "required": ["description", "command"]
                        }
                    }
                },
                "required": ["goal", "steps"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_next_step",
            "description": "Execute the next pending step in the active multi-step task. CRITICAL: After calling this and getting the result, you MUST call it again immediately for the next step if one exists.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify_step",
            "description": "Modify a step (usually the current failed step) with a new command. Use this when a step fails and you need to try an alternative approach after investigation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stepIndex": {"type": "number", "description": "Index of step to modify (0-based). If omitted, modifies current step."},
                    "newDescription": {"type": "string", "description": "Updated description"},
                    "newCommand": {"type": "string", "description": "New command to try"}
                },
                "required": ["newCommand"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "skip_step",
            "description": "Skip the current or specified step. Use this if a step is optional or cannot be completed but the task can continue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "stepIndex": {"type": "number", "description": "Index to skip (0-based). If omitted, skips current step."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_step",
            "description": "Add a new step after the current one. Use this when investigation reveals you need an additional diagnostic or preparatory step.",
            "parameters": {
                "type": "object",
                "properties": {
                    "afterStepIndex": {"type": "number", "description": "Add after this index (0-based). If omitted, adds after current step."},
                    "description": {"type": "string", "description": "What this step does"},
                    "command": {"type": "string", "description": "Shell command to execute"}
                },
                "required": ["description", "command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verify_task_completion",
            "description": "Verify that the multi-step task is complete and all objectives are met. Call this after all steps are executed for final validation.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information when stuck on an error, when more context is needed, or when the user requests it. Use this to find solutions to errors, documentation for tools/libraries, or general information. Free - no API key required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string"
                    },
                    "max_results": {
                        "type": "number",
                        "description": "Maximum number of results to return (default: 5, max: 10)",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    }
]


DEFAULT_SYSTEM_PROMPT = """You are Rogius, an AI assistant that EXECUTES commands via tools.

CRITICAL CONTEXT: The terminal commands execute on the user's local machine. Detect the OS and use appropriate commands:
- Windows: Use PowerShell commands (e.g., Get-ChildItem, New-Item, Test-Path, Get-Content, Set-Content)
- Linux/Mac: Use bash commands (e.g., ls, mkdir, cat, echo, test)
- When unsure, check $env:OS (Windows) or $OSTYPE (Linux/Mac) or uname

AUTOMATIC TASK PLANNING - WHEN TO USE MULTI-STEP:
For ANY request that involves multiple actions or sequential operations, you MUST use the multi-step workflow. DO NOT ask the user to confirm - just plan and execute.

Examples of multi-step tasks:
- "Install X and verify it works" → 3+ steps (check existing, install, verify)
- "Set up Y then configure Z" → 2+ steps (setup, configure)
- "Do A then B then C" → 3+ steps
- "Open X and close it after" → 2 steps (open, close)
- Any task with "and", "then", "afterwards", "verify", "check" usually needs multi-step

SINGLE-STEP vs MULTI-STEP DECISION:
- Simple single command → use execute_command directly
- Multiple sequential actions → use start_multistep_task
- When in doubt, use multi-step for clarity and verification

AUTONOMOUS EXECUTION PROTOCOL (CONVERSATION-BASED):
1. ANALYZE: Understand the user's goal and break it into logical steps
2. PLAN: Call start_multistep_task with a clear goal and all necessary steps
3. STEP-BY-STEP EXECUTION: You will be prompted to execute each step individually in separate conversation rounds
4. ADAPT: After each step result, you can modify/skip/add steps based on what actually happened
5. COMPLETE: Call verify_task_completion when all steps are done

CRITICAL: Each step gets its own LLM inference call. You will receive the result of step N, then be asked to execute step N+1 with full context of previous results. Adapt commands based on actual outcomes.

CRITICAL RULES:
- NEVER ask the user if they want to proceed between steps
- NEVER wait for user confirmation during multi-step execution
- ALWAYS plan the complete task upfront with start_multistep_task
- ALWAYS execute all steps automatically using execute_next_step
- ALWAYS verify results and explain what happened

INVESTIGATION PROTOCOL (when steps fail):
1. ACKNOWLEDGE: "Step X failed with [specific error]"
2. ANALYZE: Explain what the error means
3. DIAGNOSE: Run diagnostic commands via execute_command
4. WEB SEARCH: If still stuck, use web_search to find solutions online
5. ADAPT: Use modify_step, add_step, or skip_step based on findings
6. RESUME: Continue with execute_next_step

WEB SEARCH TOOL:
Use web_search when:
- Encountering unfamiliar error messages
- Need documentation for tools, libraries, or APIs
- User asks about external topics or frameworks
- Local investigation doesn't provide enough context
- The user explicitly asks you to search online

FEW-SHOT EXAMPLES - SIMPLE REQUESTS (use execute_command directly):

Example 1 - Random number:
User: "Give me a random number from 1-100"
→ execute_command({ command: "echo $((1 + RANDOM % 100))" })  # bash
→ # OR for PowerShell: Get-Random -Minimum 1 -Maximum 100

Example 2 - Current time:
User: "What time is it?"
→ execute_command({ command: "date" })  # bash
→ # OR for PowerShell: Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

Example 3 - Calculator:
User: "What is 123 * 456?"
→ execute_command({ command: "echo $((123 * 456))" })  # bash
→ # OR for PowerShell: 123 * 456

Example 4 - File creation:
User: "Create a file called test.txt"
→ execute_command({ command: "touch test.txt" })  # bash/Mac
→ # OR for PowerShell: New-Item -Path 'test.txt' -ItemType File
"""


class AIClient:
    """AI client for chat completions with tool calling."""
    
    def __init__(self, config: Optional[APIConfig] = None):
        self.config = config or APIConfig()
        if not self.config.system_prompt:
            self.config.system_prompt = DEFAULT_SYSTEM_PROMPT
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    def _build_headers(self) -> dict:
        headers = {
            "Content-Type": "application/json"
        }
        if self.config.chat_api_key:
            headers["Authorization"] = f"Bearer {self.config.chat_api_key}"
        return headers
    
    def _build_request_body(
        self,
        messages: list[ChatMessage],
        enable_tools: bool = False,
        temperature: float = 0.7
    ) -> dict:
        body = {
            "model": self.config.chat_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "temperature": temperature,
            "max_tokens": self.config.chat_context_length
        }
        # Log model being used for debugging
        print(f"[AIClient] Request using model: {self.config.chat_model}")
        
        if enable_tools:
            body["tools"] = TERMINAL_TOOLS
            body["tool_choice"] = "auto"
        
        return body
    
    async def stream_chat_completion(
        self,
        messages: list[ChatMessage],
        enable_tools: bool = False,
        signal: Optional[asyncio.Event] = None
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream chat completion with optional tool calling."""
        session = await self._get_session()
        headers = self._build_headers()
        body = self._build_request_body(messages, enable_tools)
        
        # Track accumulated tool calls
        pending_tool_calls: dict[int, ToolCall] = {}
        
        try:
            async with session.post(
                self.config.chat_endpoint,
                headers=headers,
                json=body
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API error: {response.status} - {error_text}")
                
                # Process SSE stream
                buffer = ""
                async for chunk in response.content:
                    if signal and signal.is_set():
                        break
                    
                    buffer += chunk.decode('utf-8')
                    lines = buffer.split('\n')
                    buffer = lines.pop()  # Keep incomplete line
                    
                    for line in lines:
                        line = line.strip()
                        if not line or not line.startswith('data: '):
                            continue
                        
                        data = line[6:]  # Remove 'data: ' prefix
                        if data == '[DONE]':
                            return
                        
                        try:
                            parsed = json.loads(data)
                            delta = parsed.get('choices', [{}])[0].get('delta', {})
                            finish_reason = parsed.get('choices', [{}])[0].get('finish_reason')
                            
                            content = delta.get('content')
                            tool_calls = delta.get('tool_calls')
                            
                            # Accumulate tool calls
                            if tool_calls:
                                for tc in tool_calls:
                                    idx = tc.get('index', 0)
                                    
                                    if idx in pending_tool_calls:
                                        # Merge with existing
                                        existing = pending_tool_calls[idx]
                                        if tc.get('function', {}).get('name'):
                                            existing.function_name = tc['function']['name']
                                        if tc.get('function', {}).get('arguments'):
                                            existing.function_arguments += tc['function']['arguments']
                                        if tc.get('id'):
                                            existing.id = tc['id']
                                    else:
                                        # New tool call
                                        pending_tool_calls[idx] = ToolCall(
                                            id=tc.get('id'),
                                            index=idx,
                                            type=tc.get('type', 'function'),
                                            function_name=tc.get('function', {}).get('name'),
                                            function_arguments=tc.get('function', {}).get('arguments', '')
                                        )
                            
                            if content or (finish_reason and pending_tool_calls):
                                chunk_tool_calls = list(pending_tool_calls.values()) if pending_tool_calls else None
                                if finish_reason:
                                    pending_tool_calls = {}  # Clear after yielding
                                
                                yield StreamChunk(
                                    content=content,
                                    tool_calls=chunk_tool_calls,
                                    finish_reason=finish_reason
                                )
                        
                        except json.JSONDecodeError:
                            # Ignore incomplete chunks
                            pass
        
        except Exception as e:
            yield StreamChunk(content=f"Error: {str(e)}")
            raise
    
    async def send_message(
        self,
        user_message: str,
        history: Optional[list[ChatMessage]] = None,
        enable_tools: bool = True
    ) -> tuple[str, Optional[list[ToolCall]]]:
        """Send a message and get complete response."""
        messages = history or []
        messages.append(ChatMessage(role="user", content=user_message))
        
        full_content = ""
        all_tool_calls: Optional[list[ToolCall]] = None
        
        async for chunk in self.stream_chat_completion(messages, enable_tools):
            if chunk.content:
                full_content += chunk.content
            if chunk.tool_calls:
                all_tool_calls = chunk.tool_calls
        
        return full_content, all_tool_calls
    
    async def execute_with_tools(
        self,
        user_message: str,
        tool_handlers: dict[str, Callable[[dict], Awaitable[str]]],
        history: Optional[list[ChatMessage]] = None
    ) -> str:
        """Send message and execute any tool calls automatically."""
        content, tool_calls = await self.send_message(user_message, history, enable_tools=True)
        
        if tool_calls:
            # Execute tool calls
            for tc in tool_calls:
                if tc.function_name and tc.function_name in tool_handlers:
                    try:
                        args = json.loads(tc.function_arguments) if tc.function_arguments else {}
                        result = await tool_handlers[tc.function_name](args)
                        
                        # Add tool result to content
                        content += f"\n\n[Tool {tc.function_name} result]: {result}"
                    except Exception as e:
                        content += f"\n\n[Tool {tc.function_name} error]: {str(e)}"
        
        return content
    
    async def execute_with_default_tools(
        self,
        user_message: str,
        history: Optional[list[ChatMessage]] = None
    ) -> str:
        """
        Send message and execute tool calls with built-in handlers.
        Includes web_search and other default tool implementations.
        """
        async def web_search_handler(args: dict) -> str:
            query = args.get("query", "")
            max_results = args.get("max_results", 5)
            if not query:
                return "Error: No search query provided"
            return await web_search(query, max_results)
        
        default_handlers = {
            "web_search": web_search_handler
        }
        
        return await self.execute_with_tools(user_message, default_handlers, history)
    
    async def generate_speech(
        self,
        text: str,
        voice: Optional[str] = None
    ) -> bytes:
        """Generate speech from text using TTS API."""
        session = await self._get_session()
        
        payload = {
            "input": text,
            "voice": voice or self.config.tts_voice,
            "speed": 1.0
        }
        
        headers = {"Content-Type": "application/json"}
        if self.config.tts_api_key:
            headers["Authorization"] = f"Bearer {self.config.tts_api_key}"
        
        async with session.post(
            self.config.tts_endpoint,
            headers=headers,
            json=payload
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"TTS error: {response.status} - {error_text}")
            
            return await response.read()
    
    async def fetch_models(self) -> list[str]:
        """Fetch available models from the API."""
        session = await self._get_session()
        
        base_url = self.config.chat_endpoint.replace('/chat/completions', '')
        headers = {}
        if self.config.chat_api_key:
            headers["Authorization"] = f"Bearer {self.config.chat_api_key}"
        
        try:
            async with session.get(
                f"{base_url}/models",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    return []
                
                data = await response.json()
                return [m.get('id') for m in data.get('data', []) if m.get('id')]
        
        except Exception:
            return []
    
    async def close(self):
        """Close the client session."""
        if self.session and not self.session.closed:
            await self.session.close()


class ConversationManager:
    """Manages conversation history with the AI."""
    
    def __init__(self, system_prompt: Optional[str] = None):
        self.messages: list[ChatMessage] = []
        if system_prompt:
            self.messages.append(ChatMessage(role="system", content=system_prompt))
    
    def add_user_message(self, content: str) -> None:
        self.messages.append(ChatMessage(role="user", content=content))
    
    def add_assistant_message(self, content: str) -> None:
        self.messages.append(ChatMessage(role="assistant", content=content))
    
    def add_tool_result(self, tool_name: str, result: str) -> None:
        # Add tool result as a system message or append to assistant
        self.messages.append(ChatMessage(
            role="system",
            content=f"Tool '{tool_name}' returned: {result}"
        ))
    
    def get_messages(self) -> list[ChatMessage]:
        return self.messages.copy()
    
    def clear(self) -> None:
        system_msg = None
        for m in self.messages:
            if m.role == "system":
                system_msg = m
                break
        
        self.messages = []
        if system_msg:
            self.messages.append(system_msg)
    
    def get_last_n(self, n: int) -> list[ChatMessage]:
        return self.messages[-n:] if n < len(self.messages) else self.messages.copy()


if __name__ == "__main__":
    # Test the AI client
    async def test():
        print("Testing AI Client")
        print("=" * 50)
        
        config = APIConfig(
            chat_endpoint="http://localhost:1234/v1/chat/completions",
            chat_model="llama-3.1-8b"
        )
        
        client = AIClient(config)
        
        # Test streaming
        print("\nTest 1: Streaming completion (no tools)")
        messages = [
            ChatMessage(role="system", content="You are a helpful assistant."),
            ChatMessage(role="user", content="Say 'Hello from TUI AI Client' and nothing else.")
        ]
        
        try:
            content_parts = []
            async for chunk in client.stream_chat_completion(messages, enable_tools=False):
                if chunk.content:
                    content_parts.append(chunk.content)
                    print(chunk.content, end="", flush=True)
            
            print(f"\n\nFull response: {''.join(content_parts)}")
        except Exception as e:
            print(f"\nError (expected if no API running): {e}")
        
        # Test tool parsing
        print("\n" + "=" * 50)
        print("Test 2: Tool definitions loaded")
        print(f"Number of tools: {len(TERMINAL_TOOLS)}")
        for tool in TERMINAL_TOOLS:
            print(f"  - {tool['function']['name']}")
        
        print("\n" + "=" * 50)
        print("Test complete!")
        
        await client.close()
    
    asyncio.run(test())
