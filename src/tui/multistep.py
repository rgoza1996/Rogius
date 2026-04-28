"""
Multi-Step Plan Execution for Rogius TUI

Matches the webapp's multistep.ts functionality for agentic task execution.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable
from enum import Enum
import json
from pathlib import Path


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    SKIPPED = "skipped"


class PlanStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class Step:
    """A single step in a multi-step plan."""
    id: str
    description: str
    command: str
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    dependencies: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "command": self.command,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "dependencies": self.dependencies
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Step":
        return cls(
            id=data["id"],
            description=data["description"],
            command=data["command"],
            status=StepStatus(data.get("status", "pending")),
            result=data.get("result"),
            error=data.get("error"),
            dependencies=data.get("dependencies", [])
        )


@dataclass
class MultiStepPlan:
    """A multi-step plan with a goal and executable steps."""
    id: str
    goal: str
    steps: list[Step]
    status: PlanStatus = PlanStatus.IDLE
    current_step_index: int = 0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "current_step_index": self.current_step_index,
            "started_at": self.started_at,
            "completed_at": self.completed_at
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "MultiStepPlan":
        return cls(
            id=data["id"],
            goal=data["goal"],
            steps=[Step.from_dict(s) for s in data.get("steps", [])],
            status=PlanStatus(data.get("status", "idle")),
            current_step_index=data.get("current_step_index", 0),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at")
        )


# Callback types
OnStepStart = Callable[[Step, int], Awaitable[None]]
OnStepComplete = Callable[[Step, int, str], Awaitable[None]]
OnStepError = Callable[[Step, int, str], Awaitable[None]]
StepExecutor = Callable[[str], Awaitable[tuple[str, str, int]]]  # command -> (stdout, stderr, exit_code)


def create_plan(goal: str, step_configs: list[dict]) -> MultiStepPlan:
    """Create a new multi-step plan from step configurations."""
    import time
    plan_id = f"plan-{int(time.time() * 1000)}-{id(goal) % 10000}"
    
    steps = []
    for i, config in enumerate(step_configs):
        step_id = f"step-{i}-{int(time.time() * 1000)}"
        steps.append(Step(
            id=step_id,
            description=config.get("description", f"Step {i + 1}"),
            command=config.get("command", ""),
            dependencies=config.get("dependencies", [])
        ))
    
    return MultiStepPlan(
        id=plan_id,
        goal=goal,
        steps=steps
    )


async def execute_plan(
    plan: MultiStepPlan,
    executor: StepExecutor,
    on_step_start: Optional[OnStepStart] = None,
    on_step_complete: Optional[OnStepComplete] = None,
    on_step_error: Optional[OnStepError] = None,
    signal: Optional[asyncio.Event] = None
) -> MultiStepPlan:
    """Execute a multi-step plan."""
    import time
    
    if plan.status == PlanStatus.RUNNING:
        raise ValueError("Plan is already running")
    
    plan.status = PlanStatus.RUNNING
    plan.started_at = time.time()
    
    try:
        for i in range(len(plan.steps)):
            # Check for cancellation
            if signal and signal.is_set():
                plan.status = PlanStatus.CANCELLED
                return plan
            
            step = plan.steps[i]
            plan.current_step_index = i
            
            # Skip if already completed
            if step.status == StepStatus.COMPLETED:
                continue
            
            # Check dependencies
            pending_deps = [
                dep for dep in step.dependencies
                if not any(s.id == dep and s.status == StepStatus.COMPLETED for s in plan.steps)
            ]
            
            if pending_deps:
                step.status = StepStatus.SKIPPED
                step.error = f"Dependencies not met: {', '.join(pending_deps)}"
                if on_step_error:
                    await on_step_error(step, i, step.error)
                continue
            
            # Execute step
            step.status = StepStatus.RUNNING
            if on_step_start:
                await on_step_start(step, i)
            
            try:
                stdout, stderr, exit_code = await executor(step.command)

                if exit_code == 0:
                    step.status = StepStatus.COMPLETED
                    step.result = stdout or stderr or "(no output)"
                    if on_step_complete:
                        await on_step_complete(step, i, step.result)
                else:
                    step.status = StepStatus.ERROR
                    step.error = stderr or stdout or f"Exit code: {exit_code}"
                    if on_step_error:
                        await on_step_error(step, i, step.error)

                    # Check if error is non-critical (e.g., "already exists")
                    error_str = (stderr or stdout or "").lower()
                    non_critical_errors = [
                        "already exists", "resourceexists", "file exists",
                        "directory exist", "cannot create a file when that file already exists"
                    ]
                    is_non_critical = any(err in error_str for err in non_critical_errors)

                    if is_non_critical:
                        # Mark as completed but with warning
                        step.status = StepStatus.COMPLETED
                        step.result = f"(Warning: {step.error})"
                        if on_step_complete:
                            await on_step_complete(step, i, step.result)
                    else:
                        # Stop on critical errors
                        plan.status = PlanStatus.ERROR
                        return plan

            except Exception as e:
                step.status = StepStatus.ERROR
                step.error = str(e)
                if on_step_error:
                    await on_step_error(step, i, step.error)

                # Stop on exceptions
                plan.status = PlanStatus.ERROR
                return plan
        
        # Determine final status
        all_completed = all(
            s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED)
            for s in plan.steps
        )
        any_error = any(s.status == StepStatus.ERROR for s in plan.steps)
        
        if all_completed:
            plan.status = PlanStatus.COMPLETED
        elif any_error:
            plan.status = PlanStatus.ERROR
        
        plan.completed_at = time.time()
        
    except Exception as e:
        plan.status = PlanStatus.ERROR
        raise
    
    return plan


def reset_plan(plan: MultiStepPlan) -> MultiStepPlan:
    """Reset a plan to initial state."""
    return MultiStepPlan(
        id=plan.id,
        goal=plan.goal,
        steps=[
            Step(
                id=s.id,
                description=s.description,
                command=s.command,
                status=StepStatus.PENDING,
                result=None,
                error=None,
                dependencies=s.dependencies
            )
            for s in plan.steps
        ],
        status=PlanStatus.IDLE,
        current_step_index=0
    )


def get_plan_progress(plan: MultiStepPlan) -> dict:
    """Get progress statistics for a plan."""
    total = len(plan.steps)
    completed = sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED)
    running = sum(1 for s in plan.steps if s.status == StepStatus.RUNNING)
    error = sum(1 for s in plan.steps if s.status == StepStatus.ERROR)
    pending = total - completed - running - error
    
    percentage = round((completed / total) * 100) if total > 0 else 0
    
    return {
        "total": total,
        "completed": completed,
        "running": running,
        "error": error,
        "pending": pending,
        "percentage": percentage
    }


def can_step_execute(step: Step, plan: MultiStepPlan) -> bool:
    """Check if a step can be executed (dependencies met and pending)."""
    deps_met = all(
        any(s.id == dep and s.status == StepStatus.COMPLETED for s in plan.steps)
        for dep in step.dependencies
    )
    return deps_met and step.status == StepStatus.PENDING


def modify_step(plan: MultiStepPlan, step_index: int, new_command: str, new_description: Optional[str] = None) -> MultiStepPlan:
    """Modify a step's command and optionally description."""
    if 0 <= step_index < len(plan.steps):
        step = plan.steps[step_index]
        step.command = new_command
        if new_description:
            step.description = new_description
        step.status = StepStatus.PENDING
        step.result = None
        step.error = None
        # Reset plan status to RUNNING if it was ERROR (to allow auto-continue after fixing a failed step)
        if plan.status == PlanStatus.ERROR:
            plan.status = PlanStatus.RUNNING
    return plan


def skip_step(plan: MultiStepPlan, step_index: Optional[int] = None) -> MultiStepPlan:
    """Skip a step by marking it as completed."""
    idx = step_index if step_index is not None else plan.current_step_index
    if 0 <= idx < len(plan.steps):
        plan.steps[idx].status = StepStatus.COMPLETED
        plan.steps[idx].result = "(skipped)"
    return plan


def add_step(
    plan: MultiStepPlan,
    description: str,
    command: str,
    after_step_index: Optional[int] = None
) -> MultiStepPlan:
    """Add a new step after the specified index (or current step)."""
    import time
    
    insert_index = (after_step_index if after_step_index is not None else plan.current_step_index) + 1
    
    new_step = Step(
        id=f"step-{len(plan.steps)}-{int(time.time() * 1000)}",
        description=description,
        command=command
    )
    
    plan.steps.insert(insert_index, new_step)
    return plan


def save_plan(plan: MultiStepPlan, path: Path) -> None:
    """Save a plan to disk."""
    path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")


def load_plan(path: Path) -> MultiStepPlan:
    """Load a plan from disk."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return MultiStepPlan.from_dict(data)


class PlanManager:
    """Manages active plans and their execution."""
    
    def __init__(self):
        self.active_plan: Optional[MultiStepPlan] = None
        self.plan_history: list[MultiStepPlan] = []
        self._cancel_event: Optional[asyncio.Event] = None
    
    def create_plan(self, goal: str, steps: list[dict]) -> MultiStepPlan:
        """Create and set as active."""
        plan = create_plan(goal, steps)
        self.active_plan = plan
        return plan
    
    async def execute(
        self,
        executor: StepExecutor,
        on_step_start: Optional[OnStepStart] = None,
        on_step_complete: Optional[OnStepComplete] = None,
        on_step_error: Optional[OnStepError] = None
    ) -> MultiStepPlan:
        """Execute the active plan."""
        if not self.active_plan:
            raise ValueError("No active plan")
        
        self._cancel_event = asyncio.Event()
        
        result = await execute_plan(
            self.active_plan,
            executor,
            on_step_start,
            on_step_complete,
            on_step_error,
            self._cancel_event
        )
        
        self.plan_history.append(result)
        return result
    
    def cancel(self):
        """Cancel current execution."""
        if self._cancel_event:
            self._cancel_event.set()
    
    def execute_next_step(self, executor: StepExecutor) -> Optional[asyncio.Task]:
        """Execute just the next pending step."""
        if not self.active_plan:
            return None
        
        async def run_single():
            if self.active_plan.current_step_index >= len(self.active_plan.steps):
                return self.active_plan
            
            step = self.active_plan.steps[self.active_plan.current_step_index]
            
            # Check dependencies
            for dep in step.dependencies:
                dep_step = next((s for s in self.active_plan.steps if s.id == dep), None)
                if not dep_step or dep_step.status != StepStatus.COMPLETED:
                    step.status = StepStatus.SKIPPED
                    step.error = f"Dependency not met: {dep}"
                    return self.active_plan
            
            step.status = StepStatus.RUNNING
            try:
                stdout, stderr, exit_code = await executor(step.command)
                if exit_code == 0:
                    step.status = StepStatus.COMPLETED
                    step.result = stdout or stderr or "(no output)"
                else:
                    step.status = StepStatus.ERROR
                    step.error = stderr or stdout or f"Exit code: {exit_code}"
                    self.active_plan.status = PlanStatus.ERROR
            except Exception as e:
                step.status = StepStatus.ERROR
                step.error = str(e)
                self.active_plan.status = PlanStatus.ERROR
            
            self.active_plan.current_step_index += 1
            return self.active_plan
        
        return asyncio.create_task(run_single())
    
    def modify_current_step(self, new_command: str, new_description: Optional[str] = None) -> bool:
        """Modify the current/failed step."""
        if not self.active_plan:
            return False
        
        idx = self.active_plan.current_step_index
        if 0 <= idx < len(self.active_plan.steps):
            modify_step(self.active_plan, idx, new_command, new_description)
            return True
        return False
    
    def skip_current_step(self) -> bool:
        """Skip the current step."""
        if not self.active_plan:
            return False
        
        skip_step(self.active_plan)
        self.active_plan.current_step_index += 1
        return True
    
    def add_step_after_current(self, description: str, command: str) -> bool:
        """Add a step after current."""
        if not self.active_plan:
            return False

        add_step(self.active_plan, description, command, self.active_plan.current_step_index)
        return True

    def verify_completion(self) -> dict:
        """Verify task completion status."""
        if not self.active_plan:
            return {"error": "No active plan"}
        
        progress = get_plan_progress(self.active_plan)
        
        return {
            "goal": self.active_plan.goal,
            "status": self.active_plan.status.value,
            "completed": progress["completed"],
            "total": progress["total"],
            "failed": progress["error"],
            "percentage": progress["percentage"],
            "is_complete": progress["completed"] == progress["total"]
        }
    
    def clear(self):
        """Clear active plan."""
        self.active_plan = None
        self._cancel_event = None


if __name__ == "__main__":
    # Test the multi-step functionality
    async def test():
        async def mock_executor(cmd: str) -> tuple[str, str, int]:
            print(f"  Executing: {cmd}")
            await asyncio.sleep(0.1)
            if "error" in cmd.lower():
                return ("", "Simulated error", 1)
            return (f"Output of: {cmd}", "", 0)
        
        print("Testing Multi-Step Plan Execution")
        print("=" * 50)
        
        manager = PlanManager()
        
        # Create a plan
        plan = manager.create_plan(
            "Test multi-step task",
            [
                {"description": "Step 1: Initialize", "command": "echo 'init'"},
                {"description": "Step 2: Process data", "command": "echo 'processing'"},
                {"description": "Step 3: Finalize", "command": "echo 'done'"}
            ]
        )
        
        print(f"\nCreated plan: {plan.goal}")
        print(f"Steps: {len(plan.steps)}")
        
        # Execute with callbacks
        async def on_start(step, idx):
            print(f"  → Starting: {step.description}")
        
        async def on_complete(step, idx, result):
            print(f"  ✓ Completed: {step.description}")
        
        async def on_error(step, idx, error):
            print(f"  ✗ Error: {step.description} - {error}")
        
        result = await manager.execute(mock_executor, on_start, on_complete, on_error)
        
        print(f"\nPlan status: {result.status.value}")
        print(f"Progress: {get_plan_progress(result)}")
        
        # Test verification
        verify = manager.verify_completion()
        print(f"\nVerification: {verify}")
        
        print("\n" + "=" * 50)
        print("Test complete!")
    
    asyncio.run(test())
