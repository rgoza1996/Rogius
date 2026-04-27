"""
Tool Interface - Base classes for Rogius tools.

All tools must implement the Tool interface and register with the ToolRegistry.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Callable
from enum import Enum
from pydantic import BaseModel


class ActionType(str, Enum):
    """Types of actions that tools can execute."""
    TERMINAL_COMMAND = "terminal_command"
    WEB_CRAWL = "web_crawl"
    # Future action types:
    # FILE_EDIT = "file_edit"
    # API_CALL = "api_call"


class Action(BaseModel):
    """
    A structured action to be executed by a tool.
    
    The Executor generates Actions instead of raw terminal commands.
    Tools execute Actions and return ToolResults.
    """
    type: ActionType
    payload: dict  # Tool-specific parameters
    description: str  # Human-readable summary
    timeout: int = 30
    
    class Config:
        arbitrary_types_allowed = True


class ToolResult(BaseModel):
    """
    Result of a tool execution.
    
    Tool-agnostic result that replaces CommandResult.
    Contains both human-readable output and tool-specific artifacts.
    """
    success: bool
    output: str  # Human-readable summary
    artifacts: dict  # Tool-specific results (stdout, stderr, exit_code for TerminalTool)
    error: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True


class Tool(ABC):
    """
    Base interface for all Rogius tools.
    
    Tools are responsible for:
    1. Executing actions of their specific type
    2. Providing verification helpers for the Verifier agent
    3. Applying failure fixes during retry loops
    
    Example:
        @tool(ActionType.TERMINAL_COMMAND)
        class TerminalTool(Tool):
            @property
            def action_type(self) -> ActionType:
                return ActionType.TERMINAL_COMMAND
            
            async def execute(self, action: Action, env_context: dict) -> ToolResult:
                # Execute terminal command
                pass
    """
    
    @property
    @abstractmethod
    def action_type(self) -> ActionType:
        """The action type this tool handles. Must match decorator registration."""
        pass
    
    @abstractmethod
    async def execute(self, action: Action, env_context: dict) -> ToolResult:
        """
        Execute the action and return results.
        
        Args:
            action: The Action to execute
            env_context: Environment context (os_type, shell, working_directory, etc.)
            
        Returns:
            ToolResult with success status, output, and artifacts
        """
        pass
    
    def verify(self, action: Action, result: ToolResult) -> dict:
        """
        Tool-specific verification helper.
        
        The Verifier agent calls this to get tool-specific verification data.
        Returns a dictionary of verification hints.
        
        Args:
            action: The Action that was executed
            result: The ToolResult from execution
            
        Returns:
            Dictionary with verification data (e.g., {"exit_code": 0, "failure_hint": "none"})
        """
        return {"tool_verified": result.success}
    
    def apply_failure_fix(self, action: Action, hint: str) -> Optional[Action]:
        """
        Apply a failure fix based on a hint.
        
        Called by the Executor during retry loops when a step fails.
        Returns a modified Action or None if no fix can be applied.
        
        Args:
            action: The failed Action
            hint: The failure hint (e.g., "missing_binary", "permission_denied")
            
        Returns:
            Modified Action to retry, or None if no fix available
        """
        return None
    
    def classify_failure(self, result: ToolResult) -> str:
        """
        Classify failure from ToolResult.
        
        Override this to provide tool-specific failure classification.
        
        Args:
            result: The failed ToolResult
            
        Returns:
            Failure hint string (e.g., "missing_binary", "permission_denied", "none")
        """
        if result.success:
            return "none"
        return "unknown"
    
    def get_schema(self) -> dict:
        """
        Return schema for this tool's action payload.
        
        This schema is used to dynamically build the Executor prompt.
        
        Returns:
            Dictionary with schema information including:
            - type: Action type string
            - description: Tool description
            - payload_schema: Payload structure
            - selector_strategies: (optional) Selector strategies for DOM-based tools
        """
        return {
            "type": self.action_type.value,
            "description": f"Tool for {self.action_type.value}",
            "payload_schema": {},
        }
    
    def get_examples(self) -> list[dict]:
        """
        Return example actions for this tool.
        
        These examples are used to guide the LLM in generating valid actions.
        
        Returns:
            List of example action dictionaries
        """
        return []
