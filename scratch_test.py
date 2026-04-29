import sys
import asyncio
import traceback
from pathlib import Path

sys.path.insert(0, r"d:\Rogius\src\tui")
sys.path.insert(0, r"d:\Rogius\src")

from subagents.models import AgentState, PlanStep
from subagents.executor import ExecutorAgent

async def run():
    try:
        executor = ExecutorAgent()
        state = AgentState(user_goal="Open google", session_id="123")
        state.plan = [PlanStep(id="1", description="desc", logical_action="action")]
        
        async def mock_llm(*args, **kwargs):
            return "{}"
            
        async def mock_cb(*args, **kwargs):
            pass
            
        await executor.run(state, mock_llm, 0, mock_cb)
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
