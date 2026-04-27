"""
Rogius Tools Package

Contains tool implementations and the tool registry system.
"""

# Tool interface and registry
from .tool_interface import (
    Tool,
    Action,
    ActionType,
    ToolResult,
)

from .tool_registry import (
    ToolRegistry,
    tool,
)

# Tool implementations (imports trigger @tool registration)
from .terminal_tool import TerminalTool
from .browser_tool import BrowserTool
from .web_search import web_search
from .rag_search import RAGSearchClient, RAGResult, rag_search
from .rag_indexer import ProjectIndexer, IndexConfig, index_project

__all__ = [
    # Tool system
    "Tool",
    "Action",
    "ActionType",
    "ToolResult",
    "ToolRegistry",
    "tool",
    # Tool implementations
    "TerminalTool",
    "BrowserTool",
    # Existing tools
    "web_search",
    "RAGSearchClient",
    "RAGResult",
    "rag_search",
    "ProjectIndexer",
    "IndexConfig",
    "index_project",
]
