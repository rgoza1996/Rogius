"""
Planner Agent

Agent 2: The Strategist - Creates a step-by-step plan based on user goal and environment context.
"""

import json
import sys
from typing import Optional, Callable
from pathlib import Path

# Handle imports for both package and direct execution
try:
    from .models import AgentState, AgentPhase, StepStatus, PlanStep
    from .prompts import PLANNER_SYSTEM_PROMPT
except ImportError:
    _src_dir = Path(__file__).parent.parent
    if str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))
    from subagents.models import AgentState, AgentPhase, StepStatus, PlanStep
    from subagents.prompts import PLANNER_SYSTEM_PROMPT


class PlannerAgent:
    """
    Agent 2: The Strategist
    Creates a step-by-step plan based on user goal and environment context.
    """

    async def run(self, state: AgentState, llm_call: Callable, event_callback: Optional[Callable] = None) -> AgentState:
        """
        Execute planning phase.

        Args:
            state: Current agent state with environment_context populated
            llm_call: Function to call LLM
            event_callback: Optional callback to emit events (for streaming)

        Returns:
            Updated state with plan populated
        """
        print(f"[Planner] Creating plan for goal: {state.user_goal[:50]}...")

        state.phase = AgentPhase.PLANNING

        prompt = f"""
User Goal: {state.user_goal}

Environment Context:
- OS: {state.environment_context.os_type}
- Shell: {state.environment_context.shell}
- Working Directory: {state.environment_context.working_directory}
- Username: {state.environment_context.username}
- Hostname: {state.environment_context.hostname}
- Available Commands: {', '.join(state.environment_context.available_commands[:5])}
- Relevant Existing Files: {', '.join(state.environment_context.relevant_files[:5])}

Create a detailed execution plan with logical steps.
"""

        # Emit prompt event if callback provided
        if event_callback:
            await event_callback({
                'type': 'agent_prompt',
                'agent': 'Planner',
                'system_prompt': PLANNER_SYSTEM_PROMPT,
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
                        'agent': 'Planner',
                        'chunk': chunk
                    })

            response = await llm_call(
                system_prompt=PLANNER_SYSTEM_PROMPT,
                user_prompt=prompt,
                expected_schema=dict,  # {steps: [], estimated_complexity: str, risk_factors: []}
                stream_callback=stream_chunk
            )

            # Emit final inference event
            if event_callback:
                await event_callback({
                    'type': 'agent_inference',
                    'agent': 'Planner',
                    'response': json.dumps(response, indent=2)
                })

            steps_data = response.get("steps", [])

            # Convert to PlanStep objects
            state.plan = []
            for i, step_data in enumerate(steps_data):
                step = PlanStep(
                    id=step_data.get("id", f"step_{i}"),
                    description=step_data.get("description", f"Step {i+1}"),
                    logical_action=step_data.get("logical_action", "No action specified"),
                    status=StepStatus.PENDING
                )
                state.plan.append(step)
                print(f"[Planner] Step {i}: {step.description}")
                print(f"[Planner]   Action: {step.logical_action}")

            state.execution_history.append({
                "phase": "planning",
                "steps_created": len(state.plan),
                "complexity": response.get("estimated_complexity", "unknown"),
                "risk_factors": response.get("risk_factors", [])
            })

            print(f"[Planner] Complete. Created {len(state.plan)} steps.")

        except Exception as e:
            # Fallback: create a minimal plan
            state.plan = [PlanStep(
                id="step_0",
                description="Execute user goal",
                logical_action=state.user_goal,
                status=StepStatus.PENDING
            )]
            state.execution_history.append({
                "phase": "planning",
                "error": str(e),
                "fallback": True,
                "steps_created": 1
            })
            print(f"[Planner] Warning: LLM call failed, using fallback plan: {e}")

        return state
