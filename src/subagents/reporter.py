"""
Reporter Agent

Agent 5: The Reporter - Creates user-friendly reports from execution results.
"""

import sys
from typing import Optional, Callable, Awaitable
from pathlib import Path

# Handle imports for both package and direct execution
try:
    from .models import AgentState, StepStatus
    from .prompts import REPORTER_SYSTEM_PROMPT
except ImportError:
    _src_dir = Path(__file__).parent.parent
    if str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))
    from subagents.models import AgentState, StepStatus
    from subagents.prompts import REPORTER_SYSTEM_PROMPT


class ReporterAgent:
    """
    Agent 5: The Reporter
    Creates user-friendly reports from execution results.
    """

    async def run(
        self,
        state: AgentState,
        llm_call: Callable,
        event_callback: Optional[Callable[[dict], Awaitable[None]]] = None
    ) -> tuple[AgentState, str]:
        """
        Generate a user-friendly report from execution results.

        Args:
            state: Current agent state with execution history
            llm_call: Function to call the LLM
            event_callback: Optional callback for streaming events

        Returns:
            Tuple of (updated state, report text)
        """
        # Build execution summary
        completed_steps = []
        failed_steps = []

        for i, step in enumerate(state.plan):
            if step.status == StepStatus.COMPLETED:
                completed_steps.append({
                    'index': i,
                    'description': step.description,
                    'result': step.result or '(no output)'
                })
            elif step.status == StepStatus.ERROR or step.status == StepStatus.SKIPPED:
                failed_steps.append({
                    'index': i,
                    'description': step.description,
                    'error': step.error or 'Step was skipped'
                })

        # Build the prompt
        prompt = f"""Original Goal: {state.user_goal}

Plan Summary:
Total Steps: {len(state.plan)}
Completed: {len(completed_steps)}
Failed/Skipped: {len(failed_steps)}

Successful Steps:
{chr(10).join([f"[{s['index']}] {s['description']}: {s['result'][:300]}" for s in completed_steps])}

Failed Steps:
{chr(10).join([f"[{s['index']}] {s['description']}: {s['error'][:300]}" for s in failed_steps])}

Environment Context:
OS: {state.environment_context.os_type if state.environment_context else 'unknown'}
Working Directory: {state.environment_context.working_directory if state.environment_context else 'unknown'}

Please generate a natural language report for the user. Include:
1. What was accomplished
2. What failed and why
3. The actual data/results they requested (show file listings, command outputs, etc.)
4. Whether the overall goal was achieved"""

        # Emit prompt event if callback provided
        if event_callback:
            await event_callback({
                'type': 'agent_prompt',
                'agent': 'Reporter',
                'system_prompt': REPORTER_SYSTEM_PROMPT,
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
                        'agent': 'Reporter',
                        'chunk': chunk
                    })

            # Call LLM with streaming
            llm_response = await llm_call(
                REPORTER_SYSTEM_PROMPT,
                prompt,
                stream_chunk=stream_chunk
            )

            # llm_call may return a dict - extract the actual text content
            if isinstance(llm_response, dict):
                response_text = llm_response.get('response', str(llm_response))
            else:
                response_text = str(llm_response)

            # Emit final inference event
            if event_callback:
                await event_callback({
                    'type': 'agent_inference',
                    'agent': 'Reporter',
                    'response': response_text
                })

            return state, response_text

        except Exception as e:
            error_msg = f"Error generating report: {str(e)}"
            print(f"[Reporter] {error_msg}")
            # Return basic fallback report
            fallback = f"Task completed with {len(completed_steps)} successful steps and {len(failed_steps)} failures."
            return state, fallback
