"""
Verifier Agent

Agent 4: The QA Tester - Evaluates execution results and routes the workflow.
"""

import json
import re
import sys
from typing import Optional, Callable
from pathlib import Path

# Handle imports for both package and direct execution
try:
    from .models import AgentState, AgentPhase, StepStatus, VerificationResult, FailureHint, EnvironmentContext, Action
    from .prompts import VERIFIER_SYSTEM_PROMPT
    from ..tools import ToolResult, ToolRegistry, Action
except ImportError:
    _src_dir = Path(__file__).parent.parent
    if str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))
    from subagents.models import AgentState, AgentPhase, StepStatus, VerificationResult, FailureHint, EnvironmentContext, Action
    from subagents.prompts import VERIFIER_SYSTEM_PROMPT
    from tools import ToolResult, ToolRegistry, Action


class VerifierAgent:
    """
    Agent 4: The QA Tester
    Evaluates execution results and routes the workflow.
    """

    def _extract_file_path(self, command: str, description: str, logical_action: str) -> Optional[str]:
        """
        Extract the target file path from a command or action.
        Returns the path if a file creation operation is detected, None otherwise.
        """
        # Check if this is a file creation operation
        action_text = f"{description} {logical_action}".lower()
        is_file_creation = any(keyword in action_text for keyword in [
            "create", "write", "save", "generate", "output to", "write to"
        ]) and "file" in action_text

        if not is_file_creation:
            return None

        # Try to extract path from common patterns
        # PowerShell: New-Item -Path "path", Set-Content -Path "path", Out-File -FilePath "path"
        # Bash: echo "content" > "path", echo "content" >> "path", touch "path", cat > "path"

        patterns = [
            # PowerShell patterns (more specific first)
            r'-Path\s+["\']([^"\']+)["\']',
            r'-FilePath\s+["\']([^"\']+)["\']',
            r'-Destination\s+["\']([^"\']+)["\']',
            r'New-Item\s+(?:-ItemType\s+File\s+)?(?:-Path\s+)?["\']([^"\']+)["\']',
            r'Set-Content\s+["\']([^"\']+)["\']',
            # Bash redirect patterns - match quoted path after > or >>
            r'(?:>|>>)\s*["\']([^"\']+\.[a-zA-Z0-9]+)["\']',
            # Unquoted paths: Windows (C:\path) or Unix (/home/user/file.txt)
            r'(?:>|>>)\s+([a-zA-Z]?:?\\?[^\s"\']+[^\s"\']*\.\w+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                return match.group(1)

        # Fallback: look for any quoted path with file extension
        file_ext_pattern = r'["\']([^"\']+\.(html?|txt|css|js|json|xml|py|md|yml|yaml))["\']'
        match = re.search(file_ext_pattern, command, re.IGNORECASE)
        if match:
            return match.group(1)

        return None

    def _verify_file_exists(self, file_path: str, env: EnvironmentContext) -> bool:
        """
        Actually verify that a file exists on the filesystem.
        Returns True if the file exists, False otherwise.
        """
        import os

        # Handle Windows paths
        if env.os_type == "windows":
            # Normalize Windows paths
            normalized_path = os.path.normpath(file_path)
            exists = os.path.exists(normalized_path) and os.path.isfile(normalized_path)
            print(f"[Verifier] Filesystem check: {normalized_path} exists = {exists}")
            return exists
        else:
            # Unix paths
            expanded_path = os.path.expanduser(file_path)
            exists = os.path.exists(expanded_path) and os.path.isfile(expanded_path)
            print(f"[Verifier] Filesystem check: {expanded_path} exists = {exists}")
            return exists

    async def run(
        self,
        state: AgentState,
        llm_call: Callable,
        step_index: int,
        action: Action,
        tool_result: ToolResult,
        event_callback: Optional[Callable] = None
    ) -> tuple[AgentState, VerificationResult, FailureHint]:
        """
        Verify execution result and determine next action. Returns failure hint for direct Executor correction.

        Args:
            state: Current agent state
            llm_call: Function to call LLM
            step_index: Index of step that was executed
            action: The Action that was executed
            tool_result: Result from tool execution
            event_callback: Optional callback to emit events (for streaming)

        Returns:
            Tuple of (updated_state, verification_result, failure_hint)
        """
        step = state.plan[step_index]
        print(f"[Verifier] Verifying step {step_index}: {step.description[:40]}...")

        state.phase = AgentPhase.VERIFYING

        # Check circuit breaker
        retry_key = f"step_{step_index}"
        current_retries = state.retry_counts.get(retry_key, 0)

        # Check circuit breaker (skip if infinite mode: max_retries >= 1000)
        if state.max_retries_per_step < 1000 and current_retries >= state.max_retries_per_step:
            print(f"[Verifier] CIRCUIT BREAKER: Step {step_index} exceeded max retries ({state.max_retries_per_step})")
            step.status = StepStatus.ERROR
            step.error = f"Max retries ({state.max_retries_per_step}) exceeded"
            state.execution_history.append({
                "phase": "verification",
                "step_index": step_index,
                "result": "max_retries",
                "circuit_breaker": True
            })
            return state, VerificationResult.MAX_RETRIES, FailureHint.NONE

        # Get tool-specific verification data
        tool = ToolRegistry.get(action.type)
        tool_verification = tool.verify(action, tool_result) if tool else {"tool_verified": tool_result.success}
        
        # Extract terminal-specific data for backward-compatible prompt
        artifacts = tool_result.artifacts if hasattr(tool_result, 'artifacts') else {}
        exit_code = artifacts.get("exit_code", 1 if not tool_result.success else 0)
        stdout = artifacts.get("stdout", tool_result.output if tool_result.success else "")
        stderr = artifacts.get("stderr", tool_result.error if tool_result.error else "")
        command = artifacts.get("command", action.payload.get("command", ""))
        
        prompt = f"""
Evaluate the execution result and determine the next action.

Step Details:
- Index: {step_index}
- Description: {step.description}
- Logical Action: {step.logical_action}
- Action Type: {action.type.value}
- Command Executed: {command}
- Attempt: {current_retries + 1} of {state.max_retries_per_step}

Environment:
- OS: {state.environment_context.os_type}
- Shell: {state.environment_context.shell}

Execution Result:
- Success: {tool_result.success}
- Exit Code: {exit_code}
- Output: {tool_result.output[:500] if tool_result.output else "(empty)"}
- Error: {tool_result.error[:500] if tool_result.error else "(empty)"}
- Tool Verification Data: {json.dumps(tool_verification)}

Plan Progress:
- Current Step: {step_index + 1} of {len(state.plan)}
- Remaining Steps: {len(state.plan) - step_index - 1}

Determine if this step succeeded and what to do next.
"""

        # Emit prompt event if callback provided
        if event_callback:
            await event_callback({
                'type': 'agent_prompt',
                'agent': 'Verifier',
                'system_prompt': VERIFIER_SYSTEM_PROMPT,
                'user_prompt': prompt
            })

        try:
            # Collect inference chunks for streaming
            inference_chunks = []

            async def stream_chunk(chunk: str):
                inference_chunks.append(chunk)
                if event_callback:
                    await event_callback({
                        'type': 'agent_inference_chunk',
                        'agent': 'Verifier',
                        'chunk': chunk
                    })

            response = await llm_call(
                system_prompt=VERIFIER_SYSTEM_PROMPT,
                user_prompt=prompt,
                expected_schema=dict,  # {success: bool, assessment: str, next_action: str, reason: str, ...}
                stream_callback=stream_chunk
            )

            # Emit final inference event
            if event_callback:
                await event_callback({
                    'type': 'agent_inference',
                    'agent': 'Verifier',
                    'response': json.dumps(response, indent=2)
                })

            success = response.get("success", False)
            next_action = response.get("next_action", "abort")
            suggested_fix = response.get("suggested_fix", "")
            failure_hint_str = response.get("failure_hint", "none")

        except Exception as e:
            # Fallback to simple verification with heuristic classification
            success = tool_result.success
            next_action = "continue" if success else "retry"
            suggested_fix = ""
            failure_hint_str = "none"
            # Heuristic classification for fallback
            if not success:
                stderr = (tool_result.error or "").lower()
                artifacts = tool_result.artifacts
                if artifacts and "stderr" in artifacts:
                    stderr = (artifacts["stderr"] or "").lower()
                if "command not found" in stderr or "not recognized" in stderr:
                    failure_hint_str = "missing_binary"
                elif "permission denied" in stderr or "access denied" in stderr:
                    failure_hint_str = "permission_denied"
                elif "timeout" in stderr or "timed out" in stderr:
                    failure_hint_str = "timeout"
                elif "no such file" in stderr or "cannot find" in stderr:
                    failure_hint_str = "wrong_cwd"
            print(f"[Verifier] Warning: LLM call failed, using fallback verification: {e}")

        # Filesystem verification for file creation operations
        # Use tool verification data which includes file existence checks
        if success and tool_verification:
            file_created = tool_verification.get("file_created")
            if file_created and not file_created.get("exists", True):
                # File creation failed despite tool reporting success
                success = False
                next_action = "retry"
                failure_hint_str = tool_verification.get("failure_hint", "wrong_cwd")
                print(f"[Verifier] FAIL: File not found at {file_created.get('path')} despite tool success")

        # Update step status
        artifacts = tool_result.artifacts if hasattr(tool_result, 'artifacts') else {}
        stdout = artifacts.get("stdout", tool_result.output if tool_result.success else "")
        stderr = artifacts.get("stderr", tool_result.error if tool_result.error else "")
        
        if success:
            step.status = StepStatus.COMPLETED
            step.result = stdout or stderr or "(no output)"
            step.error = None
        else:
            step.status = StepStatus.ERROR
            step.error = stderr or stdout or f"Error: {tool_result.error or 'unknown'}"
            step.retry_count = current_retries + 1
            state.retry_counts[retry_key] = step.retry_count

        # Record in history
        exit_code = artifacts.get("exit_code", 0 if tool_result.success else 1)
        state.execution_history.append({
            "phase": "verification",
            "step_index": step_index,
            "success": success,
            "exit_code": exit_code,
            "next_action": next_action
        })

        # Map next_action to VerificationResult
        result_map = {
            "continue": VerificationResult.SUCCESS,
            "complete": VerificationResult.SUCCESS,
            "retry": VerificationResult.FAIL_RETRY,
            "replan": VerificationResult.FAIL_REPLAN,
            "reinvestigate": VerificationResult.FAIL_INVESTIGATE,
            "abort": VerificationResult.MAX_RETRIES
        }

        verification_result = result_map.get(next_action, VerificationResult.FAIL_RETRY)

        # Parse and validate failure hint
        try:
            failure_hint = FailureHint(failure_hint_str)
        except ValueError:
            failure_hint = FailureHint.NONE

        # Store failure hint in step for Executor to use
        step.last_failure_hint = failure_hint

        # Apply suggested fix if retrying
        if verification_result == VerificationResult.FAIL_RETRY and suggested_fix:
            step.logical_action = suggested_fix
            print(f"[Verifier] Suggested fix applied: {suggested_fix[:50]}...")

        print(f"[Verifier] Step {step_index}: {'✓ SUCCESS' if success else '✗ FAIL'} -> {next_action} (hint: {failure_hint.value})")

        return state, verification_result, failure_hint
