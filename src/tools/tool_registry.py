"""
Tool Registry - Self-registering tool system for Rogius.

Tools register themselves using the @tool decorator pattern.
The registry maps action types to tool instances and handles execution dispatch.
"""

from typing import Dict, Optional, Type
from .tool_interface import Tool, Action, ActionType, ToolResult


class ToolRegistry:
    """
    Self-registering tool registry.
    
    Tools are registered automatically when decorated with @tool.
    The registry maps action types to tool instances.
    
    Usage:
        # Tools auto-register
        @tool(ActionType.TERMINAL_COMMAND)
        class TerminalTool(Tool):
            pass
        
        # Execute an action
        result = await ToolRegistry.execute(action, env_context)
    """
    
    _tools: Dict[ActionType, Tool] = {}
    
    @classmethod
    def register(cls, tool_instance: Tool) -> Tool:
        """
        Register a tool instance.
        
        Called automatically by the @tool decorator.
        
        Args:
            tool_instance: The tool to register
            
        Returns:
            The registered tool instance
        """
        action_type = tool_instance.action_type
        cls._tools[action_type] = tool_instance
        print(f"[ToolRegistry] Registered tool: {tool_instance.__class__.__name__} for action type: {action_type.value}")
        return tool_instance
    
    @classmethod
    def get(cls, action_type: ActionType) -> Optional[Tool]:
        """
        Get tool by action type.
        
        Args:
            action_type: The action type to look up
            
        Returns:
            The registered tool or None if not found
        """
        return cls._tools.get(action_type)
    
    @classmethod
    async def execute(cls, action: Action, env_context: dict) -> ToolResult:
        """
        Execute an action using the appropriate tool.
        
        Args:
            action: The Action to execute
            env_context: Environment context dict (os_type, shell, working_directory, etc.)
            
        Returns:
            ToolResult from execution
        """
        tool = cls.get(action.type)
        if not tool:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error=f"No tool registered for action type: {action.type.value}"
            )
        return await tool.execute(action, env_context)
    
    @classmethod
    def list_tools(cls) -> list[ActionType]:
        """
        List registered action types.
        
        Returns:
            List of registered action types
        """
        return list(cls._tools.keys())
    
    @classmethod
    def is_registered(cls, action_type: ActionType) -> bool:
        """
        Check if an action type has a registered tool.
        
        Args:
            action_type: The action type to check
            
        Returns:
            True if registered, False otherwise
        """
        return action_type in cls._tools
    
    @classmethod
    def clear(cls):
        """
        Clear all registered tools.
        
        Used primarily for testing.
        """
        cls._tools.clear()


def tool(action_type: ActionType):
    """
    Decorator to register a tool class.
    
    Usage:
        @tool(ActionType.TERMINAL_COMMAND)
        class TerminalTool(Tool):
            @property
            def action_type(self) -> ActionType:
                return ActionType.TERMINAL_COMMAND
            
            async def execute(self, action: Action, env_context: dict) -> ToolResult:
                # Implementation
                pass
    
    Args:
        action_type: The action type this tool handles
        
    Returns:
        Decorator function that registers the tool class
    """
    def decorator(cls: Type[Tool]) -> Type[Tool]:
        # Verify the class is a Tool subclass
        if not issubclass(cls, Tool):
            raise TypeError(f"Tool class {cls.__name__} must inherit from Tool")
        
        # Create instance and verify action_type matches
        instance = cls()
        if instance.action_type != action_type:
            raise ValueError(
                f"Tool {cls.__name__} action_type mismatch: "
                f"decorator specifies {action_type.value}, but tool returns {instance.action_type.value}"
            )
        
        # Register the instance
        ToolRegistry.register(instance)
        
        # Return the class (not instance) so class can still be instantiated/inherited
        return cls
    return decorator
