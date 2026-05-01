"""
FastAPI Server for Rogius Python Backend

Wraps TUI modules to provide HTTP API for the webapp.
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional, AsyncGenerator, Any
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

import aiohttp
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from shell_runner import ShellRunner, CommandResult
from multistep import (
    PlanManager, PlanStatus, StepStatus,
    create_plan, get_plan_progress, modify_step, skip_step, add_step
)
from ai_client import AIClient, APIConfig, ChatMessage, StreamChunk
from settings import TUISettings, load_settings, save_settings, get_settings_path
from launcher import OSDetector
from web_search import web_search

# Import multi-agent system
try:
    from rogius_agents import (
        run_agentic_workflow,
        RogiusMainAgent,
        AgentState,
        AgentPhase,
        StepStatus,
        INVESTIGATOR_SYSTEM_PROMPT,
        PLANNER_SYSTEM_PROMPT,
        EXECUTOR_SYSTEM_PROMPT,
        VERIFIER_SYSTEM_PROMPT
    )
    MULTI_AGENT_AVAILABLE = True
except ImportError:
    MULTI_AGENT_AVAILABLE = False
    print("Warning: Multi-agent system not available")

# Import Renamer agent
try:
    from ..subagents.renamer import RenamerAgent
    RENAMER_AVAILABLE = True
except ImportError:
    RENAMER_AVAILABLE = False
    print("Warning: Renamer agent not available")

app = FastAPI(
    title="Rogius Python Backend",
    description="FastAPI wrapper for Rogius TUI modules",
    version="1.0.0"
)

# CORS for webapp access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
shell_runner = ShellRunner()
plan_manager = PlanManager()
settings = load_settings()
print(f"[Startup] Settings loaded from: {get_settings_path()}")
print(f"[Startup] Model: {settings.chat_model}, Endpoint: {settings.chat_endpoint}")

# Check for config file mismatch (handle both camelCase and snake_case)
from pathlib import Path
project_config = Path(__file__).parent.parent.parent / "rogius.config.json"
if project_config.exists():
    try:
        import json
        with open(project_config, 'r') as f:
            project_settings = json.load(f)
        # Handle both camelCase and snake_case
        project_model = project_settings.get("chat_model") or project_settings.get("chatModel")
        if project_model and project_model != settings.chat_model:
            print(f"[WARNING] Config mismatch detected!")
            print(f"[WARNING]   settings.json:     {settings.chat_model}")
            print(f"[WARNING]   rogius.config.json:  {project_model}")
            print(f"[WARNING] Using: {settings.chat_model} (from settings.json)")
    except Exception as e:
        print(f"[Startup] Could not check project config: {e}")

ai_client: Optional[AIClient] = None

# Multi-agent global state
_agent_sessions: dict[str, Any] = {}
_main_agent: Optional[RogiusMainAgent] = None

# Renamer agent global state
_renamer_agent: Optional[Any] = None
_is_chat_streaming: bool = False


def _get_renamer_agent() -> Optional[Any]:
    """Get or create the Renamer agent."""
    global _renamer_agent
    if _renamer_agent is None and RENAMER_AVAILABLE:
        client = get_ai_client()
        _renamer_agent = RenamerAgent(client, CHAT_STORAGE_DIR)
        # Start background processor
        _renamer_agent.start(interval_seconds=5.0)
        print(f"[Renamer] Agent initialized and started")
    return _renamer_agent


def _get_main_agent() -> Optional[RogiusMainAgent]:
    """Get or create the main Rogius agent with AI client integration."""
    global _main_agent
    if _main_agent is None and MULTI_AGENT_AVAILABLE:
        # Create agent with AI client that uses settings
        client = get_ai_client()
        
        async def llm_call_wrapper(system_prompt: str, user_prompt: str, stream_callback=None, **kwargs) -> dict:
            """Wrapper to use existing AI client for LLM calls."""
            from ai_client import ChatMessage

            try:
                # EXPLICIT MODEL VERIFICATION LOGGING
                import time
                agent_name = "Unknown"
                if "Investigator" in system_prompt:
                    agent_name = "Investigator"
                elif "Planner" in system_prompt:
                    agent_name = "Planner"
                elif "Executor" in system_prompt:
                    agent_name = "Executor"
                elif "Verifier" in system_prompt:
                    agent_name = "Verifier"
                elif "Rogius" in system_prompt:
                    agent_name = "Main"
                
                print(f"[LLM CALL] Model: {client.config.chat_model}")
                print(f"[LLM CALL] Endpoint: {client.config.chat_endpoint}")
                print(f"[LLM CALL] Agent: {agent_name}")
                print(f"[LLM CALL] Time: {time.time():.3f}")

                messages = [
                    ChatMessage(role="system", content=system_prompt),
                    ChatMessage(role="user", content=user_prompt)
                ]

                content_parts = []
                async for chunk in client.stream_chat_completion(messages, enable_tools=False):
                    if chunk.content:
                        content_parts.append(chunk.content)
                        # Stream chunk if callback provided (filter out empty/whitespace-only chunks)
                        if stream_callback and chunk.content.strip():
                            await stream_callback(chunk.content)

                full_content = "".join(content_parts).strip()
                
                # Log for debugging
                print(f"[LLM] Response length: {len(full_content)} chars")
                
                # Try to parse as JSON
                try:
                    # Remove markdown code blocks if present
                    if full_content.startswith("```json"):
                        full_content = full_content[7:]
                    if full_content.startswith("```"):
                        full_content = full_content[3:]
                    if full_content.endswith("```"):
                        full_content = full_content[:-3]
                    full_content = full_content.strip()
                    
                    parsed = json.loads(full_content)
                    
                    # Check if expected schema is dict and response is missing required fields
                    expected_schema = kwargs.get('expected_schema')
                    if expected_schema == dict and isinstance(parsed, dict):
                        # For structured outputs like planner (expects 'steps'), verify key fields exist
                        if 'steps' not in parsed and 'response' in parsed:
                            # LLM returned text instead of structured JSON - raise to trigger fallback
                            raise ValueError(f"Expected structured JSON with 'steps', got text response")
                    
                    return parsed
                except json.JSONDecodeError as e:
                    # If expected structured output but got invalid JSON, raise to trigger fallback
                    expected_schema = kwargs.get('expected_schema')
                    if expected_schema == dict:
                        raise ValueError(f"Expected structured JSON output, but got non-JSON: {full_content[:200]}") from e
                    # For non-structured outputs, return as text
                    print(f"[LLM] JSON parse failed, returning as text")
                    return {"response": full_content}
            except Exception as e:
                print(f"[LLM] Error calling AI: {e}")
                # Return error so agent can handle it
                raise
        
        _main_agent = RogiusMainAgent(llm_call=llm_call_wrapper)
        print(f"[Agent] Main agent initialized with model: {client.config.chat_model}")
    
    return _main_agent


def get_ai_client() -> AIClient:
    """Get or create AI client."""
    global ai_client
    if ai_client is None:
        config = APIConfig(
            chat_endpoint=settings.chat_endpoint,
            chat_api_key=settings.chat_api_key,
            chat_model=settings.chat_model,
            chat_context_length=settings.chat_context_length,
            tts_endpoint=settings.tts_endpoint,
            tts_api_key=settings.tts_api_key,
            tts_voice=settings.tts_voice,
            auto_play_audio=settings.auto_play_audio
        )
        ai_client = AIClient(config)
        print(f"[AIClient] Created with model: {config.chat_model}")
    return ai_client


async def verify_model_consistency(expected_model: str) -> dict:
    """
    Verify that the LLM server is using the expected model.
    Returns status info to detect server-side model switching.
    """
    try:
        client = get_ai_client()
        # Fetch available models from the server
        models = await client.fetch_models()
        
        # Check if expected model is in available models
        is_available = expected_model in models
        
        # Log for debugging
        print(f"[ModelCheck] Expected: {expected_model}")
        print(f"[ModelCheck] Available: {models[:5] if models else 'None'}...")
        print(f"[ModelCheck] Match: {is_available}")
        
        return {
            "expected_model": expected_model,
            "available_models": models,
            "is_available": is_available,
            "warning": None if is_available else f"Expected model {expected_model} not in available models!"
        }
    except Exception as e:
        print(f"[ModelCheck] Error verifying model: {e}")
        return {
            "expected_model": expected_model,
            "available_models": [],
            "is_available": False,
            "warning": f"Could not verify model: {e}"
        }


# Request/Response Models
class TerminalExecuteRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    timeout: int = 30


class TerminalExecuteResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    command: str
    shell_used: str
    cwd: str


class MultistepCreateRequest(BaseModel):
    goal: str
    steps: list[dict]


class MultistepCreateResponse(BaseModel):
    plan_id: str
    goal: str
    steps_count: int
    status: str


class MultistepExecuteRequest(BaseModel):
    plan_id: str


class MultistepStatusResponse(BaseModel):
    plan_id: str
    goal: str
    status: str
    current_step: int
    total_steps: int
    progress_percentage: int
    steps: list[dict]


class AIChatRequest(BaseModel):
    messages: list[dict]
    enable_tools: bool = True
    stream: bool = True


class AIChatResponse(BaseModel):
    content: str
    tool_calls: Optional[list[dict]] = None
    finish_reason: Optional[str] = None
    web_search_results: Optional[list[dict]] = None  # Include web search results if performed


# Web search detection keywords
WEB_SEARCH_TRIGGERS = [
    "search for", "look up", "find out", "google", "what is", "who is",
    "latest news", "current events", "recent", "today", "news about",
    "wikipedia", "information about", "tell me about", "how to",
    "weather", "stock price", "price of", "universal paperclips"
]


def should_trigger_web_search(message: str) -> bool:
    """Detect if user message should trigger web search."""
    msg_lower = message.lower()
    return any(trigger in msg_lower for trigger in WEB_SEARCH_TRIGGERS)


async def perform_web_search_for_chat(query: str) -> list[dict]:
    """Perform web search and return formatted results for chat context."""
    try:
        print(f"[Chat Web Search] Searching for: {query}")
        results = await web_search(query, max_results=5)
        
        formatted_results = []
        for result in results:
            formatted_results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", "")[:300]  # Truncate long snippets
            })
        
        print(f"[Chat Web Search] Found {len(formatted_results)} results")
        return formatted_results
    except Exception as e:
        print(f"[Chat Web Search] Error: {e}")
        return []


class SettingsResponse(BaseModel):
    chat_endpoint: str
    chat_api_key: str
    chat_model: str
    chat_context_length: int
    tts_endpoint: str
    tts_api_key: str
    tts_voice: str
    auto_play_audio: bool
    max_retries: int


class SystemInfoResponse(BaseModel):
    os: str
    os_version: str
    architecture: str
    shell: str
    hostname: str
    username: str
    python_version: str
    working_directory: str
    package_manager: str
    has_sudo: bool
    node_version: str
    docker_version: str


# Startup event - verify model availability
@app.on_event("startup")
async def startup_event():
    """Verify model configuration on startup."""
    print(f"\n{'='*60}")
    print("[Startup] Verifying model configuration...")
    
    try:
        model_check = await verify_model_consistency(settings.chat_model)
        
        if model_check["is_available"]:
            print(f"[Startup] Model '{settings.chat_model}' is available on server")
        else:
            print(f"[WARNING] Model '{settings.chat_model}' NOT found on server!")
            print(f"[WARNING] Available models: {model_check.get('available_models', [])}")
            print(f"[WARNING] Server may dynamically load different models!")
        
        print(f"{'='*60}\n")
    except Exception as e:
        print(f"[Startup] Could not verify model: {e}")
        print(f"[Startup] Continuing anyway - will verify on first request")
    
    # Initialize Renamer agent
    try:
        _get_renamer_agent()
    except Exception as e:
        print(f"[Startup] Could not initialize Renamer agent: {e}")


# Health Check
@app.get("/health")
async def health_check():
    # Verify model consistency
    model_check = await verify_model_consistency(settings.chat_model)
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "model": {
            "configured": settings.chat_model,
            "endpoint": settings.chat_endpoint,
            "available_on_server": model_check["is_available"],
            "warning": model_check.get("warning")
        }
    }


# Terminal Routes
@app.post("/terminal/execute", response_model=TerminalExecuteResponse)
async def terminal_execute(request: TerminalExecuteRequest):
    """Execute a terminal command via shell_runner."""
    try:
        # Change directory if specified
        if request.cwd:
            shell_runner.change_directory(request.cwd)
        
        # Execute command
        result = shell_runner.run(request.command, timeout=request.timeout)
        
        return TerminalExecuteResponse(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            command=result.command,
            shell_used=result.shell_used,
            cwd=shell_runner.cwd
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/terminal/history")
async def terminal_history():
    """Get command history."""
    return {
        "commands": [
            {
                "command": r.command,
                "exit_code": r.exit_code,
                "stdout": r.stdout[:200] if r.stdout else "",
                "stderr": r.stderr[:200] if r.stderr else ""
            }
            for r in shell_runner.command_history[-20:]  # Last 20
        ]
    }


# Multi-Step Routes
@app.post("/multistep/create", response_model=MultistepCreateResponse)
async def multistep_create(request: MultistepCreateRequest):
    """Create a new multi-step plan."""
    try:
        plan = plan_manager.create_plan(request.goal, request.steps)
        
        return MultistepCreateResponse(
            plan_id=plan.id,
            goal=plan.goal,
            steps_count=len(plan.steps),
            status=plan.status.value
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/multistep/status")
async def multistep_status():
    """Get active plan status."""
    if not plan_manager.active_plan:
        return {"active_plan": None}
    
    plan = plan_manager.active_plan
    progress = get_plan_progress(plan)
    
    return MultistepStatusResponse(
        plan_id=plan.id,
        goal=plan.goal,
        status=plan.status.value,
        current_step=plan.current_step_index,
        total_steps=len(plan.steps),
        progress_percentage=progress["percentage"],
        steps=[
            {
                "id": s.id,
                "description": s.description,
                "command": s.command,
                "status": s.status.value,
                "result": s.result,
                "error": s.error
            }
            for s in plan.steps
        ]
    )


@app.post("/multistep/execute")
async def multistep_execute():
    """Execute the active plan."""
    if not plan_manager.active_plan:
        raise HTTPException(status_code=400, detail="No active plan")
    
    async def executor(cmd: str) -> tuple[str, str, int]:
        result = shell_runner.run(cmd)
        return (result.stdout, result.stderr, result.exit_code)
    
    try:
        result = await plan_manager.execute(
            executor,
            on_step_start=None,
            on_step_complete=None,
            on_step_error=None
        )
        
        progress = get_plan_progress(result)
        
        return {
            "plan_id": result.id,
            "status": result.status.value,
            "completed": progress["completed"],
            "total": progress["total"],
            "percentage": progress["percentage"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/multistep/execute-next")
async def multistep_execute_next():
    """Execute only the next step."""
    if not plan_manager.active_plan:
        raise HTTPException(status_code=400, detail="No active plan")
    
    async def executor(cmd: str) -> tuple[str, str, int]:
        result = shell_runner.run(cmd)
        return (result.stdout, result.stderr, result.exit_code)
    
    try:
        task = plan_manager.execute_next_step(executor)
        if task:
            await task
        
        plan = plan_manager.active_plan
        return {
            "current_step": plan.current_step_index,
            "step_status": plan.steps[plan.current_step_index - 1].status.value if plan.current_step_index > 0 else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/multistep/clear")
async def multistep_clear():
    """Clear the active plan."""
    plan_manager.clear()
    return {"status": "cleared"}


class ModifyStepRequest(BaseModel):
    stepIndex: Optional[int] = None
    newCommand: str
    newDescription: Optional[str] = None


@app.post("/multistep/modify")
async def multistep_modify(request: ModifyStepRequest):
    """Modify a step in the active plan."""
    if not plan_manager.active_plan:
        raise HTTPException(status_code=400, detail="No active plan")

    idx = request.stepIndex if request.stepIndex is not None else plan_manager.active_plan.current_step_index
    success = plan_manager.modify_current_step(request.newCommand, request.newDescription)

    if not success:
        raise HTTPException(status_code=400, detail="Invalid step index")

    return {"status": "modified", "step_index": idx}


class SkipStepRequest(BaseModel):
    stepIndex: Optional[int] = None


@app.post("/multistep/skip")
async def multistep_skip(request: SkipStepRequest):
    """Skip a step in the active plan."""
    if not plan_manager.active_plan:
        raise HTTPException(status_code=400, detail="No active plan")

    from multistep import skip_step
    idx = request.stepIndex if request.stepIndex is not None else plan_manager.active_plan.current_step_index
    skip_step(plan_manager.active_plan, request.stepIndex)
    plan_manager.active_plan.current_step_index += 1

    return {"status": "skipped", "step_index": idx}


class AddStepRequest(BaseModel):
    afterStepIndex: Optional[int] = None
    description: str
    command: str


@app.post("/multistep/add")
async def multistep_add(request: AddStepRequest):
    """Add a step to the active plan."""
    if not plan_manager.active_plan:
        raise HTTPException(status_code=400, detail="No active plan")

    from multistep import add_step
    insert_index = (request.afterStepIndex if request.afterStepIndex is not None else plan_manager.active_plan.current_step_index) + 1
    add_step(plan_manager.active_plan, request.description, request.command, request.afterStepIndex)

    return {"status": "added", "insert_index": insert_index}


class MultistepAgenticRequest(BaseModel):
    goal: str
    steps: list[dict]
    max_iterations: int = 50


@app.post("/multistep/execute-agentic-stream")
async def multistep_execute_agentic_stream(request: MultistepAgenticRequest):
    """
    Execute a plan with AI agent loop - STREAMING version.
    Uses the multi-agent workflow (Investigator, Planner, Executor, Verifier).
    Yields real-time updates as SSE events.
    """
    from fastapi.responses import StreamingResponse
    import json

    if not MULTI_AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Multi-agent system not available")

    async def event_generator():
        """Generate SSE events using the multi-agent streaming workflow."""
        
        # Get the main agent with proper LLM configuration
        agent = _get_main_agent()
        if not agent:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to initialize agent'})}\n\n"
            return

        try:
            # Stream events from the multi-agent workflow
            async for event in agent.execute_streaming(request.goal, max_retries=settings.max_retries):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


# AI Chat Routes
@app.post("/ai/chat")
async def ai_chat(request: AIChatRequest):
    """Chat with AI (non-streaming). Performs web search if user query triggers it."""
    try:
        client = get_ai_client()
        
        # Check if last user message should trigger web search
        web_search_results = None
        last_user_message = None
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break
        
        if last_user_message and should_trigger_web_search(last_user_message):
            web_search_results = await perform_web_search_for_chat(last_user_message)
        
        # Build messages with web search context if available
        messages = [ChatMessage(role=m["role"], content=m["content"]) for m in request.messages]
        
        # If web search results found, inject them into system context
        if web_search_results:
            search_context = "Web search results for this query:\n"
            for i, result in enumerate(web_search_results, 1):
                search_context += f"{i}. {result['title']}: {result['snippet'][:200]}\n"
            
            # Prepend to system message or add as system message
            has_system = any(m.role == "system" for m in messages)
            if has_system:
                for m in messages:
                    if m.role == "system":
                        m.content += f"\n\n{search_context}"
                        break
            else:
                messages.insert(0, ChatMessage(role="system", content=search_context))
        
        content_parts = []
        tool_calls = []
        
        async for chunk in client.stream_chat_completion(messages, enable_tools=request.enable_tools):
            if chunk.content:
                content_parts.append(chunk.content)
            if chunk.tool_calls:
                tool_calls.extend([tc.to_dict() for tc in chunk.tool_calls])
        
        return AIChatResponse(
            content="".join(content_parts),
            tool_calls=tool_calls if tool_calls else None,
            web_search_results=web_search_results
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai/chat/stream")
async def ai_chat_stream(request: AIChatRequest):
    """Chat with AI (streaming SSE). Performs web search if user query triggers it."""
    global _is_chat_streaming
    try:
        client = get_ai_client()
        
        # Check if last user message should trigger web search
        web_search_results = None
        last_user_message = None
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break
        
        if last_user_message and should_trigger_web_search(last_user_message):
            web_search_results = await perform_web_search_for_chat(last_user_message)
        
        # Build messages with web search context if available
        messages = [ChatMessage(role=m["role"], content=m["content"]) for m in request.messages]
        
        # If web search results found, inject them into system context
        if web_search_results:
            search_context = "Web search results for this query:\n"
            for i, result in enumerate(web_search_results, 1):
                search_context += f"{i}. {result['title']}: {result['snippet'][:200]}\n"
            
            # Prepend to system message or add as system message
            has_system = any(m.role == "system" for m in messages)
            if has_system:
                for m in messages:
                    if m.role == "system":
                        m.content += f"\n\n{search_context}"
                        break
            else:
                messages.insert(0, ChatMessage(role="system", content=search_context))
        
        # Set streaming active
        _is_chat_streaming = True
        if _renamer_agent:
            _renamer_agent.set_streaming_state(True)
        
        async def event_generator():
            try:
                # Yield web search results first if available
                if web_search_results:
                    yield f"data: {json.dumps({'web_search_results': web_search_results})}\n\n"
                
                async for chunk in client.stream_chat_completion(messages, enable_tools=request.enable_tools):
                    data = {}
                    if chunk.content:
                        data["content"] = chunk.content
                    if chunk.tool_calls:
                        data["tool_calls"] = [tc.to_dict() for tc in chunk.tool_calls]
                    if chunk.finish_reason:
                        data["finish_reason"] = chunk.finish_reason
                    
                    if data:
                        yield f"data: {json.dumps(data)}\n\n"
                
                yield "data: [DONE]\n\n"
            finally:
                # Always clear streaming state when done
                global _is_chat_streaming
                _is_chat_streaming = False
                if _renamer_agent:
                    _renamer_agent.set_streaming_state(False)
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream"
        )
    except Exception as e:
        # Clear streaming state on error
        _is_chat_streaming = False
        if _renamer_agent:
            _renamer_agent.set_streaming_state(False)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ai/models")
async def ai_models():
    """List available AI models."""
    try:
        client = get_ai_client()
        models = await client.fetch_models()
        return {"models": models}
    except Exception as e:
        return {"models": [], "error": str(e)}


# TTS Routes
class TTSRequest(BaseModel):
    """Request to generate speech."""
    input: str
    voice: Optional[str] = None
    speed: float = 1.0


class TTSCheckResponse(BaseModel):
    """Response from TTS server health check."""
    available: bool
    endpoint: str
    error: Optional[str] = None


@app.get("/tts/check", response_model=TTSCheckResponse)
async def tts_check():
    """Check if the TTS server is reachable."""
    try:
        client = get_ai_client()
        session = await client._get_session()
        
        # Try to connect to the TTS server with a short timeout
        async with session.get(
            settings.tts_endpoint.replace('/v1/audio/speech', '/health'),
            timeout=aiohttp.ClientTimeout(total=5)
        ) as response:
            if response.status == 200:
                return TTSCheckResponse(available=True, endpoint=settings.tts_endpoint)
            else:
                return TTSCheckResponse(
                    available=False, 
                    endpoint=settings.tts_endpoint,
                    error=f"Health check returned status {response.status}"
                )
    except Exception as e:
        return TTSCheckResponse(
            available=False,
            endpoint=settings.tts_endpoint,
            error=str(e)
        )


@app.post("/tts/speech")
async def tts_speech(request: TTSRequest):
    """
    Generate speech from text using the remote KokoroTTS server.
    Proxies the request to roggoz via tailscale and returns the audio data.
    """
    try:
        client = get_ai_client()
        
        # Generate speech using the AI client's generate_speech method
        audio_data = await client.generate_speech(
            text=request.input,
            voice=request.voice or settings.tts_voice
        )
        
        # Return the audio data as a WAV blob
        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=speech.wav",
                "X-TTS-Voice": request.voice or settings.tts_voice
            }
        )
    except Exception as e:
        error_msg = str(e)
        if "Cannot connect" in error_msg or "Connection refused" in error_msg:
            raise HTTPException(
                status_code=503,
                detail=f"KokoroTTS server is not running on roggoz. Please start it with: python3 ~/kokoro-server.py"
            )
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {error_msg}")


# Settings Routes
@app.get("/settings", response_model=SettingsResponse)
async def get_settings():
    """Get current settings."""
    return SettingsResponse(
        chat_endpoint=settings.chat_endpoint,
        chat_api_key=settings.chat_api_key,
        chat_model=settings.chat_model,
        chat_context_length=settings.chat_context_length,
        tts_endpoint=settings.tts_endpoint,
        tts_api_key=settings.tts_api_key,
        tts_voice=settings.tts_voice,
        auto_play_audio=settings.auto_play_audio,
        max_retries=settings.max_retries
    )


@app.post("/settings")
async def update_settings(new_settings: SettingsResponse):
    """Update settings."""
    global settings, ai_client, _main_agent
    
    settings.chat_endpoint = new_settings.chat_endpoint
    settings.chat_api_key = new_settings.chat_api_key
    settings.chat_model = new_settings.chat_model
    settings.chat_context_length = new_settings.chat_context_length
    settings.tts_endpoint = new_settings.tts_endpoint
    settings.tts_api_key = new_settings.tts_api_key
    settings.tts_voice = new_settings.tts_voice
    settings.auto_play_audio = new_settings.auto_play_audio
    settings.max_retries = new_settings.max_retries
    
    save_settings(settings)
    
    # Reset AI client and main agent to pick up new settings
    ai_client = None
    _main_agent = None
    
    print(f"[Settings] Updated - Model: {settings.chat_model}, Endpoint: {settings.chat_endpoint}")
    
    return {"status": "updated", "model": settings.chat_model}


# System Info Route
@app.get("/system/info", response_model=SystemInfoResponse)
async def system_info():
    """Get system information."""
    info = OSDetector.get_system_info()
    return SystemInfoResponse(
        os=info["os"],
        os_version=info["os_version"],
        architecture=info["architecture"],
        shell=info["shell"],
        hostname=info["hostname"],
        username=info["username"],
        python_version=info["python_version"],
        working_directory=shell_runner.cwd,
        package_manager=info.get("package_manager", "unknown"),
        has_sudo=info.get("has_sudo", False),
        node_version=info.get("node_version", "not installed"),
        docker_version=info.get("docker_version", "not installed")
    )


# Chat Storage Routes
CHAT_STORAGE_DIR = Path("D:/Rogius/src/chat_history")
CHAT_INDEX_FILE = CHAT_STORAGE_DIR / "index.json"

# Ensure storage directory exists
CHAT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class ChatSession(BaseModel):
    id: str
    title: str
    messages: list[dict]
    createdAt: int
    updatedAt: int
    userTitled: Optional[bool] = None
    userMessageCount: Optional[int] = None


class ChatIndexEntry(BaseModel):
    id: str
    title: str
    createdAt: int
    updatedAt: int
    messageCount: int


class ChatListResponse(BaseModel):
    chats: list[ChatIndexEntry]


def _load_chat_index() -> list:
    """Load the chat index from file."""
    if not CHAT_INDEX_FILE.exists():
        return []
    try:
        with open(CHAT_INDEX_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def _save_chat_index(index: list):
    """Save the chat index to file."""
    with open(CHAT_INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)


def _get_chat_file_path(chat_id: str) -> Path:
    """Get the file path for a specific chat."""
    safe_chat_id = os.path.basename(chat_id)
    return CHAT_STORAGE_DIR / f"{safe_chat_id}.json"


@app.get("/chats", response_model=ChatListResponse)
async def list_chats():
    """List all chat sessions."""
    index = _load_chat_index()
    return ChatListResponse(chats=index)


@app.get("/chats/{chat_id}")
async def get_chat(chat_id: str):
    """Get a specific chat by ID."""
    chat_file = _get_chat_file_path(chat_id)
    if not chat_file.exists():
        raise HTTPException(status_code=404, detail="Chat not found")
    
    try:
        with open(chat_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load chat: {str(e)}")


@app.post("/chats")
async def save_chat_endpoint(chat: ChatSession):
    """Save a chat session."""
    try:
        # Save the full chat to its own file
        chat_file = _get_chat_file_path(chat.id)
        with open(chat_file, 'w', encoding='utf-8') as f:
            json.dump(chat.dict(), f, indent=2)
        
        # Update the index
        index = _load_chat_index()
        existing = next((i for i, c in enumerate(index) if c["id"] == chat.id), None)
        
        entry = {
            "id": chat.id,
            "title": chat.title,
            "createdAt": chat.createdAt,
            "updatedAt": chat.updatedAt,
            "messageCount": len(chat.messages)
        }
        
        if existing is not None:
            index[existing] = entry
        else:
            index.append(entry)
        
        _save_chat_index(index)
        return {"status": "saved", "id": chat.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save chat: {str(e)}")


@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str):
    """Delete a specific chat."""
    try:
        # Remove chat file
        chat_file = _get_chat_file_path(chat_id)
        if chat_file.exists():
            chat_file.unlink()
        
        # Update index
        index = _load_chat_index()
        index = [c for c in index if c["id"] != chat_id]
        _save_chat_index(index)
        
        return {"status": "deleted", "id": chat_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete chat: {str(e)}")


@app.delete("/chats")
async def clear_all_chats():
    """Clear all chat history."""
    try:
        # Delete all chat files
        for chat_file in CHAT_STORAGE_DIR.glob("*.json"):
            if chat_file.name != "index.json":
                chat_file.unlink()
        
        # Clear index
        if CHAT_INDEX_FILE.exists():
            CHAT_INDEX_FILE.unlink()
        
        return {"status": "cleared", "count": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear chats: {str(e)}")


@app.get("/chats/storage/info")
async def storage_info():
    """Get storage information."""
    try:
        index = _load_chat_index()
        total_size = sum(
            _get_chat_file_path(c["id"]).stat().st_size 
            for c in index 
            if _get_chat_file_path(c["id"]).exists()
        )
        
        return {
            "location": str(CHAT_STORAGE_DIR),
            "chatCount": len(index),
            "totalSizeBytes": total_size,
            "totalSizeKB": round(total_size / 1024, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get storage info: {str(e)}")


# =============================================================================
# Multi-Agent System Routes (Rogius Architecture)
# =============================================================================

class MultiAgentExecuteRequest(BaseModel):
    """Request to execute a goal through the multi-agent system."""
    goal: str
    session_id: Optional[str] = None


class MultiAgentExecuteResponse(BaseModel):
    """Response from multi-agent execution."""
    session_id: str
    success: bool
    phase: str
    completed_steps: int
    total_steps: int
    failed_steps: int
    skipped_steps: int
    environment: dict
    final_report: Optional[str] = None
    error_message: Optional[str] = None


class MultiAgentStatusResponse(BaseModel):
    """Status of a multi-agent session."""
    session_id: str
    phase: str
    user_goal: str
    current_step: int
    total_steps: int
    environment: dict
    execution_history: list


class AgentSystemPromptsResponse(BaseModel):
    """System prompts for all agents."""
    investigator: str
    planner: str
    executor: str
    verifier: str
    rogius_main: str


@app.get("/agents/prompts", response_model=AgentSystemPromptsResponse)
async def get_agent_prompts():
    """Get the system prompts for all agents."""
    if not MULTI_AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Multi-agent system not available")
    
    from rogius_agents import ROGIUS_SYSTEM_PROMPT
    
    return AgentSystemPromptsResponse(
        investigator=INVESTIGATOR_SYSTEM_PROMPT,
        planner=PLANNER_SYSTEM_PROMPT,
        executor=EXECUTOR_SYSTEM_PROMPT,
        verifier=VERIFIER_SYSTEM_PROMPT,
        rogius_main=ROGIUS_SYSTEM_PROMPT
    )


@app.post("/agents/execute", response_model=MultiAgentExecuteResponse)
async def agents_execute(request: MultiAgentExecuteRequest, background_tasks: BackgroundTasks):
    """
    Execute a goal through the multi-agent system.
    
    This runs the full Rogius workflow:
    1. Investigator probes environment
    2. Planner creates step-by-step plan
    3. Executor translates to commands
    4. Verifier evaluates and routes
    5. Loop until complete or max retries
    """
    if not MULTI_AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Multi-agent system not available")
    
    try:
        agent = _get_main_agent()
        if not agent:
            raise HTTPException(status_code=503, detail="Failed to initialize agent")
        
        # Execute the workflow
        final_state = await agent.execute(request.goal, request.session_id)
        
        # Store session for later retrieval
        _agent_sessions[final_state.session_id] = final_state
        
        return MultiAgentExecuteResponse(
            session_id=final_state.session_id,
            success=final_state.phase == AgentPhase.COMPLETE,
            phase=final_state.phase.value,
            completed_steps=sum(1 for s in final_state.plan if s.status == StepStatus.COMPLETED),
            total_steps=len(final_state.plan),
            failed_steps=sum(1 for s in final_state.plan if s.status == StepStatus.ERROR),
            skipped_steps=sum(1 for s in final_state.plan if s.status == StepStatus.SKIPPED),
            environment={
                "os": final_state.environment_context.os_type,
                "shell": final_state.environment_context.shell,
                "working_directory": final_state.environment_context.working_directory
            },
            final_report=final_state.final_report,
            error_message=final_state.error_message
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")


@app.get("/agents/sessions/{session_id}", response_model=MultiAgentStatusResponse)
async def get_agent_session(session_id: str):
    """Get the status of a specific agent session."""
    if not MULTI_AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Multi-agent system not available")
    
    if session_id not in _agent_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = _agent_sessions[session_id]
    
    return MultiAgentStatusResponse(
        session_id=state.session_id,
        phase=state.phase.value,
        user_goal=state.user_goal,
        current_step=state.current_step_index,
        total_steps=len(state.plan),
        environment={
            "os": state.environment_context.os_type,
            "shell": state.environment_context.shell,
            "working_directory": state.environment_context.working_directory
        },
        execution_history=state.execution_history
    )


@app.get("/agents/sessions")
async def list_agent_sessions():
    """List all active agent sessions."""
    if not MULTI_AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Multi-agent system not available")
    
    return {
        "sessions": [
            {
                "session_id": sid,
                "phase": state.phase.value,
                "user_goal": state.user_goal[:50] + "..." if len(state.user_goal) > 50 else state.user_goal,
                "completed_steps": sum(1 for s in state.plan if s.status == StepStatus.COMPLETED),
                "total_steps": len(state.plan)
            }
            for sid, state in _agent_sessions.items()
        ]
    }


@app.delete("/agents/sessions/{session_id}")
async def delete_agent_session(session_id: str):
    """Delete a specific agent session."""
    if not MULTI_AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Multi-agent system not available")
    
    if session_id not in _agent_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del _agent_sessions[session_id]
    return {"status": "deleted", "session_id": session_id}


@app.post("/agents/execute-stream")
async def agents_execute_stream(request: MultiAgentExecuteRequest):
    """
    Execute a goal through the multi-agent system with streaming updates.
    
    Returns SSE events for each phase/step.
    """
    if not MULTI_AGENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Multi-agent system not available")
    
    async def event_generator():
        agent = None
        try:
            agent = _get_main_agent()
            if not agent:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Failed to initialize agent'})}\n\n"
                return
            
            # Use the new streaming execution method
            async for event in agent.execute_streaming(request.goal, request.session_id, max_retries=settings.max_retries):
                yield f"data: {json.dumps(event)}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@app.get("/agents/health")
async def agents_health():
    """Check if multi-agent system is available."""
    return {
        "available": MULTI_AGENT_AVAILABLE,
        "components": {
            "rogius_agents": MULTI_AGENT_AVAILABLE,
            "ai_client": ai_client is not None or settings.chat_endpoint != ""
        }
    }


# =============================================================================
# Renamer Agent Routes
# =============================================================================

class RenamerEnqueueRequest(BaseModel):
    """Request to enqueue a chat for renaming."""
    chat_id: str


class RenamerToggleRequest(BaseModel):
    """Request to toggle chat eligibility."""
    chat_id: str
    eligible: bool


class RenamerStatusResponse(BaseModel):
    """Response with renamer status."""
    available: bool
    queue_length: int
    processing: bool
    streaming_active: bool
    last_processed: Optional[str]
    queue: list[str]


@app.get("/renamer/status", response_model=RenamerStatusResponse)
async def renamer_status():
    """Get current Renamer agent status."""
    agent = _get_renamer_agent()
    if not agent:
        return RenamerStatusResponse(
            available=False,
            queue_length=0,
            processing=False,
            streaming_active=False,
            last_processed=None,
            queue=[]
        )
    
    status = agent.get_status()
    return RenamerStatusResponse(
        available=True,
        queue_length=status["queue_length"],
        processing=status["processing"],
        streaming_active=status["streaming_active"],
        last_processed=status["last_processed"],
        queue=status["queue"]
    )


@app.post("/renamer/enqueue")
async def renamer_enqueue(request: RenamerEnqueueRequest):
    """Add a chat to the Renamer queue."""
    agent = _get_renamer_agent()
    if not agent:
        raise HTTPException(status_code=503, detail="Renamer agent not available")
    
    added = agent.enqueue_chat(request.chat_id)
    return {
        "status": "enqueued" if added else "already_in_queue",
        "chat_id": request.chat_id,
        "queue_position": agent.get_queue().index(request.chat_id) + 1 if request.chat_id in agent.get_queue() else None
    }


@app.post("/renamer/dequeue")
async def renamer_dequeue(request: RenamerEnqueueRequest):
    """Remove a chat from the Renamer queue (e.g., user manually titled)."""
    agent = _get_renamer_agent()
    if not agent:
        raise HTTPException(status_code=503, detail="Renamer agent not available")
    
    removed = agent.dequeue_chat(request.chat_id)
    return {
        "status": "dequeued" if removed else "not_in_queue",
        "chat_id": request.chat_id
    }


@app.post("/renamer/toggle-eligibility")
async def renamer_toggle_eligibility(request: RenamerToggleRequest):
    """
    Toggle chat eligibility for Renamer queue.
    If eligible=False, sets userTitled=True.
    If eligible=True, removes userTitled flag.
    """
    safe_chat_id = os.path.basename(request.chat_id)
    chat_file = CHAT_STORAGE_DIR / f"{safe_chat_id}.json"
    if not chat_file.exists():
        raise HTTPException(status_code=404, detail="Chat not found")
    
    try:
        with open(chat_file, 'r', encoding='utf-8') as f:
            chat = json.load(f)
        
        chat["userTitled"] = not request.eligible
        chat["updatedAt"] = int(datetime.now().timestamp() * 1000)
        
        with open(chat_file, 'w', encoding='utf-8') as f:
            json.dump(chat, f, indent=2)
        
        # Also update index
        index_file = CHAT_STORAGE_DIR / "index.json"
        if index_file.exists():
            with open(index_file, 'r', encoding='utf-8') as f:
                index = json.load(f)
            for entry in index:
                if entry["id"] == request.chat_id:
                    entry["updatedAt"] = chat["updatedAt"]
                    break
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2)
        
        return {
            "status": "updated",
            "chat_id": request.chat_id,
            "eligible": request.eligible,
            "userTitled": chat["userTitled"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update chat: {str(e)}")


@app.post("/renamer/process")
async def renamer_process():
    """Manually trigger processing of the next chat in queue."""
    agent = _get_renamer_agent()
    if not agent:
        raise HTTPException(status_code=503, detail="Renamer agent not available")
    
    if agent.state.streaming_active:
        return {
            "status": "skipped",
            "reason": "streaming_active",
            "message": "Cannot process while streaming is active"
        }
    
    processed = await agent.process_next()
    return {
        "status": "processed" if processed else "no_chats",
        "chat_id": processed
    }


@app.get("/renamer/queue")
async def renamer_queue():
    """Get current queue of chats waiting to be renamed."""
    agent = _get_renamer_agent()
    if not agent:
        raise HTTPException(status_code=503, detail="Renamer agent not available")
    
    return {
        "queue": agent.get_queue(),
        "count": len(agent.get_queue())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
