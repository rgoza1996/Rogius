import json
from enum import Enum
from typing import Optional, Any
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

# =============================================================================
# STATE MANAGEMENT
# =============================================================================

class StepStatus(str, Enum):
    """Status of a plan step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    SKIPPED = "skipped"

class PlanStatus(str, Enum):
    """Status of the overall plan execution."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"

class AgentPhase(str, Enum):
    """Current phase in the agent loop."""
    INITIALIZING = "initializing"
    INVESTIGATING = "investigating"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    FAILED = "failed"

class VerificationResult(str, Enum):
    """Result of verification step."""
    SUCCESS = "success"
    FAIL_RETRY = "fail_retry"  # Retry same step
    FAIL_REPLAN = "fail_replan"  # Go back to planner
    FAIL_INVESTIGATE = "fail_investigate"  # Environment changed, re-investigate
    MAX_RETRIES = "max_retries"  # Circuit breaker triggered

class FailureHint(str, Enum):
    """Structured failure classification for direct Executor correction."""
    NONE = "none"
    MISSING_BINARY = "missing_binary"      # Command not found - try full path/alternative
    PERMISSION_DENIED = "permission_denied"  # Need elevated privileges
    WRONG_CWD = "wrong_cwd"              # Working directory incorrect
    MISSING_ENV_VAR = "missing_env_var"  # Environment variable not set
    INVALID_ARGUMENTS = "invalid_arguments"  # Arguments malformed
    HOST_UNREACHABLE = "host_unreachable"    # Network/SSH connection failed
    TIMEOUT = "timeout"                  # Command timed out
    MISSING_DEPENDENCY = "missing_dependency"  # Required tool/library not installed


class ActionType(str, Enum):
    """Types of actions that tools can execute."""
    TERMINAL_COMMAND = "terminal_command"
    WEB_CRAWL = "web_crawl"
    # Future action types:
    # FILE_EDIT = "file_edit"


class Action(BaseModel):
    """
    A structured action to be executed by a tool.
    The Executor generates Actions instead of raw terminal commands.
    """
    type: ActionType
    payload: dict  # Tool-specific parameters
    description: str  # Human-readable summary
    timeout: int = 30
    
    class Config:
        arbitrary_types_allowed = True


class PlanStep(BaseModel):
    """A single step in the execution plan."""
    id: str
    description: str
    logical_action: str  # What to do (e.g., "Create file with content")
    action: Optional[Action] = None  # Structured action (filled by Executor)
    command: Optional[str] = None  # Legacy: actual terminal command (deprecated, kept for compatibility)
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    last_failure_hint: FailureHint = FailureHint.NONE  # Hint from Verifier
    applied_fixes: list[str] = Field(default_factory=list)  # Track what was tried

class EnvironmentContext(BaseModel):
    """Context gathered by the Investigator."""
    os_type: str = "unknown"
    os_name: str = "unknown"
    shell: str = "unknown"
    working_directory: str = ""
    username: str = ""
    hostname: str = ""
    available_commands: list[str] = Field(default_factory=list)
    relevant_files: list[str] = Field(default_factory=list)
    environment_variables: dict[str, str] = Field(default_factory=dict)
    web_search_results: list[dict] = Field(default_factory=list)
    rag_search_results: list[dict] = Field(default_factory=list)

class AgentState(BaseModel):
    """
    Shared state passed between all agents in the pipeline.
    This is the single source of truth for the entire workflow.
    """
    # Core identifiers
    session_id: str
    user_goal: str
    
    # Execution tracking
    phase: AgentPhase = AgentPhase.INITIALIZING
    plan: list[PlanStep] = Field(default_factory=list)
    current_step_index: int = 0
    
    # Context and history
    environment_context: EnvironmentContext = Field(default_factory=EnvironmentContext)
    execution_history: list[dict] = Field(default_factory=list)
    max_history_entries: int = 10  # Keep only last 10 entries to save tokens
    
    # Retry and circuit breaker tracking
    retry_counts: dict[str, int] = Field(default_factory=dict)  # step_id -> retry_count
    max_retries_per_step: int = 999
    global_retry_count: int = 0
    max_global_retries: int = 20
    
    # Final result
    final_report: Optional[str] = None
    error_message: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True

    def add_history_entry(self, entry: dict):
        """Add entry to execution history, truncating if needed."""
        self.execution_history.append(entry)
        if len(self.execution_history) > self.max_history_entries:
            self.execution_history = self.execution_history[-self.max_history_entries:]
