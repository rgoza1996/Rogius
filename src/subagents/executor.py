"""
Executor Agent

Agent 3: The Hands - Translates logical steps into exact terminal commands.
"""

import json
import sys
from typing import Optional, Callable
from pathlib import Path

# Handle imports for both package and direct execution
try:
    from .models import AgentState, AgentPhase, StepStatus, PlanStep, EnvironmentContext, FailureHint, Action, ActionType
    from .prompts import EXECUTOR_SYSTEM_PROMPT
    from ..tui.launcher import OSDetector, OperatingSystem
    from ..tui.shell_runner import ShellRunner, CommandResult
    from ..tools import ToolRegistry, ToolResult
except ImportError:
    _src_dir = Path(__file__).parent.parent
    if str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))
    from subagents.models import AgentState, AgentPhase, StepStatus, PlanStep, EnvironmentContext, FailureHint, Action, ActionType
    from subagents.prompts import EXECUTOR_SYSTEM_PROMPT
    from tui.launcher import OSDetector, OperatingSystem
    from tui.shell_runner import ShellRunner, CommandResult
    from tools import ToolRegistry, ToolResult


class ExecutorAgent:
    """
    Agent 3: The Hands
    Translates logical steps into exact terminal commands.
    """

    async def run(
        self,
        state: AgentState,
        llm_call: Callable,
        step_index: Optional[int] = None,
        event_callback: Optional[Callable] = None
    ) -> tuple[AgentState, Action, ToolResult]:
        """
        Execute the current (or specified) step.

        Args:
            state: Current agent state with plan populated
            llm_call: Function to call LLM
            step_index: Index of step to execute (default: current_step_index)
            event_callback: Optional callback to emit events (for streaming)

        Returns:
            Tuple of (updated_state, action, tool_result)
        """
        idx = step_index if step_index is not None else state.current_step_index

        if idx >= len(state.plan):
            # No more steps - return empty action and result
            empty_action = Action(
                type=ActionType.TERMINAL_COMMAND,
                payload={"command": ""},
                description="No more steps to execute",
                timeout=0
            )
            empty_result = ToolResult(
                success=False,
                output="No more steps to execute",
                artifacts={},
                error="No more steps to execute"
            )
            return state, empty_action, empty_result

        step = state.plan[idx]
        print(f"[Executor] Executing step {idx}: {step.description[:40]}...")

        state.phase = AgentPhase.EXECUTING
        step.status = StepStatus.RUNNING

        # Check if we have a failure hint from previous attempt - apply targeted fix
        hinted_command = None
        if step.retry_count > 0 and step.last_failure_hint != FailureHint.NONE:
            hinted_command = self._apply_hinted_fix(step, state.environment_context)
            if hinted_command:
                step.applied_fixes.append(f"{step.last_failure_hint.value}: {hinted_command}")
                print(f"[Executor] Applied hint-based fix: {step.last_failure_hint.value}")

        # Build tool schemas dynamically from ToolRegistry
        tool_schemas = self._build_tool_schemas()
        
        prompt = f"""
Translate this logical step into a structured Action object.

Environment:
- OS: {state.environment_context.os_type}
- Shell: {state.environment_context.shell}
- Working Directory: {state.environment_context.working_directory}

Step Details:
- Description: {step.description}
- Logical Action: {step.logical_action}

Previous Attempts: {step.retry_count}

AVAILABLE TOOLS:
{tool_schemas}

Generate an Action object using the appropriate tool type.
"""

        # Emit prompt event if callback provided
        if event_callback:
            await event_callback({
                'type': 'agent_prompt',
                'agent': 'Executor',
                'system_prompt': EXECUTOR_SYSTEM_PROMPT,
                'user_prompt': prompt
            })

        action = None
        
        try:
            # If we have a hinted command, create Action directly without LLM call
            if hinted_command:
                print(f"[Executor] Using hint-based command: {hinted_command[:60]}...")
                action = Action(
                    type=ActionType.TERMINAL_COMMAND,
                    payload={"command": hinted_command},
                    description=f"Retry with fix: {step.last_failure_hint.value}",
                    timeout=60  # Extended timeout for retried commands
                )
            else:
                # Collect inference chunks for streaming
                inference_chunks = []

                async def stream_chunk(chunk: str):
                    inference_chunks.append(chunk)
                    if event_callback:
                        await event_callback({
                            'type': 'agent_inference_chunk',
                            'agent': 'Executor',
                            'chunk': chunk
                        })

                response = await llm_call(
                    system_prompt=EXECUTOR_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    expected_schema=dict,
                    stream_callback=stream_chunk
                )

                # Emit final inference event
                if event_callback:
                    await event_callback({
                        'type': 'agent_inference',
                        'agent': 'Executor',
                        'response': json.dumps(response, indent=2)
                    })

                # Parse Action from response
                action_type_str = response.get("type", "terminal_command")
                action = Action(
                    type=ActionType(action_type_str),
                    payload=response.get("payload", {}),
                    description=response.get("description", ""),
                    timeout=response.get("timeout", 30)
                )

                # Debug logging
                print(f"[Executor] Generated action: {action.type.value}")
                print(f"[Executor] Payload: {json.dumps(action.payload)}")
                print(f"[Executor] Description: {action.description}")

        except Exception as e:
            # Fallback: create basic command from logical action
            fallback_command = self._generate_fallback_command(
                step.logical_action,
                state.environment_context
            )
            action = Action(
                type=ActionType.TERMINAL_COMMAND,
                payload={"command": fallback_command},
                description="Fallback command generation",
                timeout=30
            )
            print(f"[Executor] Warning: LLM call failed, using fallback command: {e}")

        # Execute via ToolRegistry
        result = await ToolRegistry.execute(action, state.environment_context.dict())

        # Update step with action and result (backward compatible)
        step.action = action
        step.command = action.payload.get("command", "")  # Legacy support

        state.execution_history.append({
            "phase": "execution",
            "step_index": idx,
            "action_type": action.type.value,
            "command": action.payload.get("command", ""),
            "success": result.success
        })

        return state, action, result

    def _generate_fallback_command(self, logical_action: str, env: EnvironmentContext) -> str:
        """Generate a basic command from logical action when LLM fails."""
        action_lower = logical_action.lower()
        is_windows = env.os_type == "windows"

        # Simple pattern matching for common operations
        if "create" in action_lower and "file" in action_lower:
            # Extract path and content if possible
            if is_windows:
                return f'New-Item -ItemType File -Path "file.txt" -Force'
            else:
                return "touch file.txt"

        elif "delete" in action_lower or "remove" in action_lower:
            if is_windows:
                return 'Remove-Item -Path "file.txt" -ErrorAction SilentlyContinue'
            else:
                return "rm -f file.txt"

        elif "copy" in action_lower:
            if is_windows:
                return 'Copy-Item -Path "source" -Destination "dest"'
            else:
                return "cp source dest"

        elif "list" in action_lower or "show" in action_lower:
            if is_windows:
                return "Get-ChildItem"
            else:
                return "ls -la"

        # Default: echo the action
        if is_windows:
            return f'Write-Output "Attempting: {logical_action}"'
        else:
            return f'echo "Attempting: {logical_action}"'

    def _apply_hinted_fix(self, step: PlanStep, env: EnvironmentContext) -> Optional[str]:
        """
        Apply targeted fix based on failure hint from Verifier.
        Returns the fixed command or None if no fix can be applied.
        """
        hint = step.last_failure_hint
        last_command = step.command or ""
        is_windows = env.os_type == "windows"

        # Track that we're attempting this fix
        if hint == FailureHint.MISSING_BINARY:
            # Try to find the binary with 'which' or common alternatives
            binary_name = last_command.split()[0] if last_command else ""
            if not binary_name:
                return None

            # Common alternative names
            alternatives = {
                "python": ["python3", "python3.11", "python3.10", "/usr/bin/python3"],
                "pip": ["pip3", "python3 -m pip", "/usr/bin/pip3"],
                "node": ["nodejs", "/usr/bin/node"],
                "npm": ["/usr/bin/npm"],
                "docker": ["/usr/bin/docker"],
                "kubectl": ["oc", "/usr/local/bin/kubectl"],
                "ssh": ["/usr/bin/ssh", "/usr/local/bin/ssh"],
                "git": ["/usr/bin/git", "/usr/local/bin/git"],
                "code": ["/usr/bin/code", "/usr/local/bin/code"],
            }

            if binary_name in alternatives:
                for alt in alternatives[binary_name]:
                    if is_windows:
                        return last_command.replace(binary_name, alt, 1)
                    else:
                        # Try with 'which' to verify existence
                        return f"which {alt} && {last_command.replace(binary_name, alt, 1)}"

            # Try with full path search
            if not is_windows:
                return f"$(which {binary_name} 2>/dev/null || echo '{binary_name}') {last_command[len(binary_name):]}"

        elif hint == FailureHint.PERMISSION_DENIED:
            # Retry with sudo (Unix) or check if elevated (Windows)
            if is_windows:
                # Try with elevated privileges indication
                return f'powershell -Command "Start-Process {last_command} -Verb runAs"'
            else:
                # Try with sudo
                return f"sudo {last_command}"

        elif hint == FailureHint.WRONG_CWD:
            # Try from home directory or common locations
            if not is_windows:
                return f"cd ~ && {last_command}"
            else:
                return f"cd %USERPROFILE% && {last_command}"

        elif hint == FailureHint.MISSING_ENV_VAR:
            # Common environment variables that might be needed
            if "HOME" in last_command or "~" in last_command:
                if is_windows:
                    return f"set HOME=%USERPROFILE% && {last_command}"
                else:
                    return f'export HOME=${{HOME:-~}} && {last_command}'
            elif "PATH" in step.error or "not found" in (step.error or "").lower():
                if is_windows:
                    return f'set PATH=%PATH%;C:\\Windows\\System32 && {last_command}'
                else:
                    return f'export PATH="$PATH:/usr/local/bin:/usr/bin" && {last_command}'

        elif hint == FailureHint.TIMEOUT:
            # Increase timeout - handled by caller, but we can add nohang
            if not is_windows:
                return f"timeout 300 {last_command} || true"

        elif hint == FailureHint.HOST_UNREACHABLE:
            # Add retry logic or alternative connection
            if "ssh" in last_command.lower():
                # Add connection timeout and retry
                return last_command.replace("ssh ", "ssh -o ConnectTimeout=30 -o ConnectionAttempts=3 ", 1)

        elif hint == FailureHint.INVALID_ARGUMENTS:
            # Strip problematic flags - try basic version
            # Remove common problematic flags
            simplified = last_command
            for flag in ["--color", "-v", "--verbose", "--progress", "-i", "--interactive"]:
                simplified = simplified.replace(f" {flag}", "").replace(f"{flag} ", "")
            return simplified if simplified != last_command else None

        elif hint == FailureHint.MISSING_DEPENDENCY:
            # Try to install missing dependency (common ones)
            if "npm" in last_command or "node" in last_command:
                return f"npm install && {last_command}" if not is_windows else last_command
            elif "pip" in last_command or "python" in last_command:
                pkg = last_command.split()[-1] if last_command.split() else "package"
                return f"pip install {pkg} && {last_command}" if not is_windows else last_command

        # No fix could be applied
        return None

    def _build_tool_schemas(self) -> str:
        """
        Build formatted tool schemas from ToolRegistry.
        
        This dynamically generates the tool documentation for the Executor prompt,
        so adding new tools doesn't require modifying prompts.py.
        
        Returns:
            Formatted string with all tool schemas and examples
        """
        from ..tools import ToolRegistry
        
        schemas = []
        
        for action_type in ToolRegistry.list_tools():
            tool = ToolRegistry.get(action_type)
            if tool is None:
                continue
            
            schema = tool.get_schema()
            examples = tool.get_examples()
            
            # Build schema section
            schema_text = f"""
{schema['type'].upper()}
{schema['description']}

PAYLOAD:
{json.dumps(schema.get('payload_schema', {}), indent=2)}
"""
            
            # Add selector strategies if available (for DOM-based tools)
            if 'selector_strategies' in schema:
                schema_text += f"\nSELECTOR STRATEGIES:\n"
                for strategy in schema['selector_strategies']:
                    schema_text += f"- {strategy}\n"
            
            # Add operation types if available (for tools with multiple operations)
            if 'operation_types' in schema:
                schema_text += f"\nOPERATION TYPES:\n"
                for op_type in schema['operation_types']:
                    schema_text += f"- {op_type}\n"
            
            # Add OS-specific syntax if available
            if 'os_specific_syntax' in schema:
                schema_text += f"\nOS-SPECIFIC SYNTAX:\n"
                for os_name, syntax in schema['os_specific_syntax'].items():
                    schema_text += f"- {os_name}: {syntax}\n"
            
            # Add failure hints if available
            if 'failure_hints' in schema:
                schema_text += f"\nFAILURE HINTS:\n"
                for hint in schema['failure_hints']:
                    schema_text += f"- {hint}\n"
            
            # Add examples
            if examples:
                schema_text += f"\nEXAMPLES:\n"
                for i, example in enumerate(examples, 1):
                    schema_text += f"\nExample {i}: {example.get('description', 'N/A')}\n"
                    schema_text += json.dumps(example, indent=2)
                    schema_text += "\n"
            
            schemas.append(schema_text)
        
        return "\n\n".join(schemas) if schemas else "No tools registered."
