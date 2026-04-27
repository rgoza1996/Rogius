"""
Rogius Main Agent

Agent 0: The Project Manager - Orchestrates the entire multi-agent workflow.
"""

import asyncio
import sys
import time
from typing import Optional, Callable, AsyncGenerator, Any
from pathlib import Path

# Handle imports for both package and direct execution
try:
    from .models import AgentState, AgentPhase, StepStatus, VerificationResult
    from .llm_client import call_llm
    from .investigator import InvestigatorAgent
    from .planner import PlannerAgent
    from .executor import ExecutorAgent
    from .verifier import VerifierAgent
    from .reporter import ReporterAgent
    # Import tools to register them (TerminalTool auto-registers via @tool decorator)
    from ..tools import TerminalTool, ToolRegistry, ActionType
except ImportError:
    _src_dir = Path(__file__).parent.parent
    if str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))
    from subagents.models import AgentState, AgentPhase, StepStatus, VerificationResult
    from subagents.llm_client import call_llm
    from subagents.investigator import InvestigatorAgent
    from subagents.planner import PlannerAgent
    from subagents.executor import ExecutorAgent
    from subagents.verifier import VerifierAgent
    from subagents.reporter import ReporterAgent
    # Import tools to register them (TerminalTool auto-registers via @tool decorator)
    from tools import TerminalTool, ToolRegistry, ActionType


class RogiusMainAgent:
    """
    Agent 0: The Project Manager
    Orchestrates the entire multi-agent workflow.
    """

    def __init__(self, llm_call: Optional[Callable] = None):
        """
        Initialize the main agent.

        Args:
            llm_call: Optional custom LLM call function. If not provided,
                     uses the default call_llm function.
        """
        self.llm_call = llm_call or call_llm
        self.investigator = InvestigatorAgent()
        self.planner = PlannerAgent()
        self.executor = ExecutorAgent()
        self.verifier = VerifierAgent()
        self.reporter = ReporterAgent()

    async def execute(self, user_goal: str, session_id: Optional[str] = None) -> AgentState:
        """
        Execute the complete multi-agent workflow.

        Args:
            user_goal: The user's task/request
            session_id: Optional session identifier

        Returns:
            Final agent state with results
        """
        start_time = time.time()

        # Initialize state
        state = AgentState(
            session_id=session_id or f"session_{int(time.time())}",
            user_goal=user_goal,
            phase=AgentPhase.INITIALIZING
        )

        print(f"\n{'='*60}")
        print(f"[Rogius] Starting new session: {state.session_id}")
        print(f"[Rogius] Goal: {user_goal}")
        print(f"{'='*60}\n")

        try:
            # Phase 1: Investigation
            state = await self.investigator.run(state, self.llm_call)

            # Phase 2: Planning
            state = await self.planner.run(state, self.llm_call)

            if not state.plan:
                state.phase = AgentPhase.FAILED
                state.error_message = "No plan could be created"
                return state

            # Phase 3-4: Execution Loop
            max_iterations = 100  # Global safety limit
            iteration = 0

            while iteration < max_iterations:
                iteration += 1
                state.global_retry_count += 1

                if state.global_retry_count > state.max_global_retries:
                    state.phase = AgentPhase.FAILED
                    state.error_message = f"Global retry limit ({state.max_global_retries}) exceeded"
                    break

                # Check if all steps are complete
                if state.current_step_index >= len(state.plan):
                    break

                step = state.plan[state.current_step_index]

                # Skip completed steps
                if step.status == StepStatus.COMPLETED:
                    state.current_step_index += 1
                    continue

                # Skip steps that exceeded retries
                if step.status == StepStatus.ERROR:
                    retry_key = f"step_{state.current_step_index}"
                    if state.retry_counts.get(retry_key, 0) >= state.max_retries_per_step:
                        print(f"[Rogius] Skipping step {state.current_step_index} (max retries exceeded)")
                        step.status = StepStatus.SKIPPED
                        state.current_step_index += 1
                        continue

                # Execute current step
                state, action, tool_result = await self.executor.run(
                    state, self.llm_call, state.current_step_index
                )

                # Verify result with action and tool_result
                state, verification, failure_hint = await self.verifier.run(
                    state, self.llm_call, state.current_step_index, action, tool_result
                )

                # Route based on verification
                if verification == VerificationResult.SUCCESS:
                    # Move to next step
                    state.current_step_index += 1

                elif verification == VerificationResult.MAX_RETRIES:
                    # Skip this step and move on
                    step.status = StepStatus.SKIPPED
                    state.current_step_index += 1

                elif verification == VerificationResult.FAIL_RETRY:
                    # Retry same step (command was already updated by verifier)
                    print(f"[Rogius] Retrying step {state.current_step_index} (attempt {step.retry_count})")

                elif verification == VerificationResult.FAIL_REPLAN:
                    # Go back to planner with current context
                    print(f"[Rogius] Replanning from step {state.current_step_index}")
                    # Mark remaining steps as pending for replanning
                    for i in range(state.current_step_index, len(state.plan)):
                        state.plan[i].status = StepStatus.PENDING
                    state = await self.planner.run(state, self.llm_call)

                elif verification == VerificationResult.FAIL_INVESTIGATE:
                    # Re-investigate environment
                    print(f"[Rogius] Re-investigating environment")
                    state = await self.investigator.run(state, self.llm_call)
                    # Reset to first pending step
                    state.current_step_index = 0

            # Phase 5: Finalize
            execution_time = time.time() - start_time

            completed_steps = sum(1 for s in state.plan if s.status == StepStatus.COMPLETED)
            failed_steps = sum(1 for s in state.plan if s.status == StepStatus.ERROR)
            skipped_steps = sum(1 for s in state.plan if s.status == StepStatus.SKIPPED)

            if failed_steps == 0 and state.current_step_index >= len(state.plan):
                state.phase = AgentPhase.COMPLETE
            elif completed_steps > 0:
                state.phase = AgentPhase.COMPLETE  # Partial completion
            else:
                state.phase = AgentPhase.FAILED

            # Generate final report
            state.final_report = self._generate_final_report(
                state, execution_time, completed_steps, failed_steps, skipped_steps
            )

            print(f"\n{'='*60}")
            print(f"[Rogius] Session Complete: {state.session_id}")
            print(f"[Rogius] Steps: {completed_steps} completed, {failed_steps} failed, {skipped_steps} skipped")
            print(f"[Rogius] Time: {execution_time:.2f}s")
            print(f"{'='*60}\n")

        except Exception as e:
            state.phase = AgentPhase.FAILED
            state.error_message = str(e)
            print(f"[Rogius] FATAL ERROR: {e}")
            import traceback
            traceback.print_exc()

        return state

    async def execute_streaming(
        self,
        user_goal: str,
        session_id: Optional[str] = None,
        max_retries: int = 999
    ) -> AsyncGenerator[dict, None]:
        """
        Execute the workflow with streaming progress updates.

        Yields events:
        - {'type': 'start', 'goal': str, 'total_steps': int}
        - {'type': 'step_start', 'step': int, 'description': str}
        - {'type': 'step_complete', 'step': int, 'result': str, 'output': str}
        - {'type': 'step_error', 'step': int, 'error': str, 'output': str}
        - {'type': 'complete', 'status': str, 'completed': int, 'total': int}
        - {'type': 'error', 'message': str}
        - {'type': 'agent_prompt', 'agent': str, 'system_prompt': str, 'user_prompt': str}
        - {'type': 'agent_inference', 'agent': str, 'response': str}
        """
        start_time = time.time()

        # Initialize state
        state = AgentState(
            session_id=session_id or f"session_{int(time.time())}",
            user_goal=user_goal,
            phase=AgentPhase.INITIALIZING,
            max_retries_per_step=max_retries
        )

        try:
            # Phase 1: Investigation
            yield {'type': 'phase', 'phase': 'investigation', 'message': 'Probing environment...'}

            # Define a wrapper to collect investigator events
            investigator_events = []
            async def investigator_callback(event: dict):
                if event.get('type') == 'agent_prompt':
                    event['from_agent'] = 'Rogius'
                investigator_events.append(event)

            state = await self.investigator.run(state, self.llm_call, investigator_callback)

            # Yield any collected events from investigator
            for event in investigator_events:
                yield event

            # Phase 2: Planning
            yield {'type': 'phase', 'phase': 'planning', 'message': 'Creating execution plan...'}

            planner_events = []
            async def planner_callback(event: dict):
                if event.get('type') == 'agent_prompt':
                    event['from_agent'] = 'Investigator'
                planner_events.append(event)

            state = await self.planner.run(state, self.llm_call, planner_callback)

            # Yield any collected events from planner
            for event in planner_events:
                yield event

            if not state.plan:
                yield {'type': 'error', 'message': 'No plan could be created'}
                return

            total_steps = len(state.plan)
            yield {'type': 'start', 'goal': user_goal, 'total_steps': total_steps}

            # Phase 3-4: Execution Loop with streaming
            max_iterations = 100
            iteration = 0
            completed = 0

            while iteration < max_iterations:
                iteration += 1
                state.global_retry_count += 1

                if state.global_retry_count > state.max_global_retries:
                    yield {'type': 'error', 'message': f'Global retry limit ({state.max_global_retries}) exceeded'}
                    break

                if state.current_step_index >= len(state.plan):
                    break

                step = state.plan[state.current_step_index]

                # Skip completed steps
                if step.status == StepStatus.COMPLETED:
                    state.current_step_index += 1
                    completed += 1
                    continue

                # Skip steps that exceeded retries (unless infinite mode: max_retries >= 1000)
                if step.status == StepStatus.ERROR and state.max_retries_per_step < 1000:
                    retry_key = f"step_{state.current_step_index}"
                    if state.retry_counts.get(retry_key, 0) >= state.max_retries_per_step:
                        step.status = StepStatus.SKIPPED
                        state.current_step_index += 1
                        continue

                # Yield step start
                yield {
                    'type': 'step_start',
                    'step': state.current_step_index,
                    'description': step.description
                }

                # Execute step with event capture
                executor_events = []
                async def executor_callback(event: dict):
                    if event.get('type') == 'agent_prompt':
                        # Executor receives prompts from Planner (first run) or Verifier (retries)
                        if step.retry_count > 0:
                            event['from_agent'] = 'Verifier (retry)'
                        else:
                            event['from_agent'] = 'Planner'
                    executor_events.append(event)

                state, action, result = await self.executor.run(
                    state, self.llm_call, state.current_step_index, executor_callback
                )

                # Yield executor events
                for event in executor_events:
                    yield event

                # Get output from ToolResult (backward compatible with CommandResult)
                artifacts = result.artifacts if hasattr(result, 'artifacts') else {}
                stdout = artifacts.get('stdout', result.output if result.success else '')
                stderr = artifacts.get('stderr', result.error if result.error else '')
                output = stdout or stderr or '(no output)'
                
                # Get command from action for backward compatibility
                command = action.payload.get('command', '') if action else ''

                # Verify result with Verifier agent
                verifier_events = []
                async def verifier_callback(event: dict):
                    if event.get('type') == 'agent_prompt':
                        event['from_agent'] = 'Executor'
                    verifier_events.append(event)

                state, verification, failure_hint = await self.verifier.run(
                    state, self.llm_call, state.current_step_index, action, result, verifier_callback
                )

                # Yield verifier events
                for event in verifier_events:
                    yield event

                # Route based on verification result
                if verification == VerificationResult.SUCCESS:
                    step.status = StepStatus.COMPLETED
                    step.result = output
                    completed += 1
                    print(f"[Step {state.current_step_index}] Command: {command}")
                    print(f"[Step {state.current_step_index}] Output: {output[:200]}")
                    yield {
                        'type': 'step_complete',
                        'step': state.current_step_index,
                        'result': step.result[:200] if step.result else '(ok)',
                        'output': output[:500]  # First 500 chars
                    }
                    state.current_step_index += 1
                elif verification == VerificationResult.MAX_RETRIES:
                    step.status = StepStatus.SKIPPED
                    yield {
                        'type': 'step_warn',
                        'step': state.current_step_index,
                        'message': 'Max retries exceeded, skipping step',
                        'output': output[:500]
                    }
                    state.current_step_index += 1
                elif verification == VerificationResult.FAIL_RETRY:
                    step.status = StepStatus.PENDING
                    step.retry_count += 1
                    retry_key = f"step_{state.current_step_index}"
                    state.retry_counts[retry_key] = state.retry_counts.get(retry_key, 0) + 1
                    yield {'type': 'retry', 'step': state.current_step_index, 'attempt': step.retry_count, 'hint': failure_hint.value}
                    # Will retry same step - Verifier may have updated the command
                elif verification == VerificationResult.FAIL_REPLAN:
                    yield {'type': 'phase', 'phase': 'planning', 'message': 'Replanning due to verification failure...'}
                    # Go back to planner
                    replan_events = []
                    async def replan_callback(event: dict):
                        if event.get('type') == 'agent_prompt':
                            event['from_agent'] = 'Verifier'
                        replan_events.append(event)

                    # Mark remaining steps as pending for replanning
                    for i in range(state.current_step_index, len(state.plan)):
                        state.plan[i].status = StepStatus.PENDING

                    state = await self.planner.run(state, self.llm_call, replan_callback)

                    for event in replan_events:
                        yield event

                    if not state.plan:
                        yield {'type': 'error', 'message': 'Replanning failed'}
                        break
                elif verification == VerificationResult.FAIL_INVESTIGATE:
                    yield {'type': 'phase', 'phase': 'investigation', 'message': 'Re-investigating environment...'}
                    # Re-investigate
                    reinvestigate_events = []
                    async def reinvestigate_callback(event: dict):
                        if event.get('type') == 'agent_prompt':
                            event['from_agent'] = 'Verifier'
                        reinvestigate_events.append(event)

                    state = await self.investigator.run(state, self.llm_call, reinvestigate_callback)

                    for event in reinvestigate_events:
                        yield event

                    # Reset to first pending step
                    state.current_step_index = 0

                # Brief pause for UI updates
                await asyncio.sleep(0.01)

            # Finalize
            execution_time = time.time() - start_time
            completed_steps = sum(1 for s in state.plan if s.status == StepStatus.COMPLETED)
            failed_steps = sum(1 for s in state.plan if s.status == StepStatus.ERROR)

            if failed_steps == 0:
                state.phase = AgentPhase.COMPLETE
            elif completed_steps > 0:
                state.phase = AgentPhase.COMPLETE
            else:
                state.phase = AgentPhase.FAILED

            yield {
                'type': 'complete',
                'status': state.phase.value,
                'completed': completed_steps,
                'total': len(state.plan),
                'percentage': round((completed_steps / len(state.plan)) * 100) if state.plan else 0
            }

            # Phase 5: Reporting - Generate user-friendly summary
            yield {'type': 'phase', 'phase': 'reporting', 'message': 'Generating report...'}

            reporter_events = []
            async def reporter_callback(event: dict):
                if event.get('type') == 'agent_prompt':
                    event['from_agent'] = 'Rogius'
                reporter_events.append(event)

            state, report = await self.reporter.run(state, self.llm_call, reporter_callback)

            # Yield reporter events
            for event in reporter_events:
                yield event

            # Emit final report
            yield {
                'type': 'report',
                'report': report
            }

        except Exception as e:
            yield {'type': 'error', 'message': str(e)}

    def _generate_final_report(
        self,
        state: AgentState,
        execution_time: float,
        completed: int,
        failed: int,
        skipped: int
    ) -> str:
        """Generate the final execution report."""

        report_lines = [
            "# Rogius Execution Report",
            "",
            f"**Session ID:** {state.session_id}",
            f"**User Goal:** {state.user_goal}",
            f"**Status:** {'✓ Complete' if state.phase == AgentPhase.COMPLETE else '✗ Failed'}",
            f"**Execution Time:** {execution_time:.2f} seconds",
            "",
            "## Summary",
            f"- **Completed Steps:** {completed}",
            f"- **Failed Steps:** {failed}",
            f"- **Skipped Steps:** {skipped}",
            f"- **Total Steps:** {len(state.plan)}",
            "",
            "## Environment",
            f"- **OS:** {state.environment_context.os_type}",
            f"- **Shell:** {state.environment_context.shell}",
            f"- **Working Directory:** {state.environment_context.working_directory}",
            "",
            "## Execution Details",
        ]

        for i, step in enumerate(state.plan):
            icon = "✓" if step.status == StepStatus.COMPLETED else "✗" if step.status == StepStatus.ERROR else "○"
            report_lines.append(f"### Step {i+1}: {icon} {step.description}")
            if step.command:
                report_lines.append(f"**Command:** `{step.command}`")
            if step.result:
                result_preview = step.result[:200] + "..." if len(step.result) > 200 else step.result
                report_lines.append(f"**Result:** {result_preview}")
            if step.error:
                report_lines.append(f"**Error:** {step.error}")
            report_lines.append("")

        if state.error_message:
            report_lines.extend([
                "## Error",
                state.error_message,
                ""
            ])

        report_lines.append("## Execution History")
        for entry in state.execution_history:
            report_lines.append(f"- {entry}")

        return "\n".join(report_lines)


async def run_agentic_workflow(
    user_goal: str,
    llm_call: Optional[Callable] = None,
    session_id: Optional[str] = None
) -> dict:
    """
    Main entry point for the agentic workflow.

    Args:
        user_goal: The user's task or request
        llm_call: Optional custom LLM call function
        session_id: Optional session identifier

    Returns:
        Dict with final state information
    """
    agent = RogiusMainAgent(llm_call=llm_call)
    final_state = await agent.execute(user_goal, session_id)

    return {
        "session_id": final_state.session_id,
        "user_goal": final_state.user_goal,
        "phase": final_state.phase.value,
        "success": final_state.phase == AgentPhase.COMPLETE,
        "plan_steps_count": len(final_state.plan),
        "completed_steps": sum(1 for s in final_state.plan if s.status == StepStatus.COMPLETED),
        "failed_steps": sum(1 for s in final_state.plan if s.status == StepStatus.ERROR),
        "skipped_steps": sum(1 for s in final_state.plan if s.status == StepStatus.SKIPPED),
        "environment": {
            "os": final_state.environment_context.os_type,
            "shell": final_state.environment_context.shell,
            "working_directory": final_state.environment_context.working_directory
        },
        "final_report": final_state.final_report,
        "error_message": final_state.error_message,
        "execution_history": final_state.execution_history
    }
