"""
Rogius Multi-Agent System - Subagents Package

A modular agentic workflow with 6 specialized agents:
1. InvestigatorAgent - Environment Scout
2. PlannerAgent - Strategy Creator
3. ExecutorAgent - Command Generator
4. VerifierAgent - QA Tester
5. ReporterAgent - Results Summarizer
6. RogiusMainAgent - Project Manager (orchestrates all agents)

Usage:
    from subagents import RogiusMainAgent, run_agentic_workflow
"""

import sys
from pathlib import Path

# Handle imports for both package usage and direct execution
try:
    from .models import (
        StepStatus,
        PlanStatus,
        AgentPhase,
        VerificationResult,
        FailureHint,
        PlanStep,
        EnvironmentContext,
        AgentState,
    )
    from .prompts import (
        INVESTIGATOR_SYSTEM_PROMPT,
        PLANNER_SYSTEM_PROMPT,
        EXECUTOR_SYSTEM_PROMPT,
        VERIFIER_SYSTEM_PROMPT,
        REPORTER_SYSTEM_PROMPT,
        ROGIUS_SYSTEM_PROMPT,
    )
    from .llm_client import call_llm
    from .investigator import InvestigatorAgent
    from .planner import PlannerAgent
    from .executor import ExecutorAgent
    from .verifier import VerifierAgent
    from .reporter import ReporterAgent
    from .main import RogiusMainAgent, run_agentic_workflow
    from .renamer import RenamerAgent
    
    # RAG Tools
    from ..tools.rag_search import RAGSearchClient, RAGResult, rag_search
    from ..tools.rag_indexer import ProjectIndexer, IndexConfig, index_project
except ImportError:
    # Fall back to absolute imports (when run directly)
    _this_dir = Path(__file__).parent
    _src_dir = _this_dir.parent
    if str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))
    
    from subagents.models import (
        StepStatus,
        PlanStatus,
        AgentPhase,
        VerificationResult,
        FailureHint,
        PlanStep,
        EnvironmentContext,
        AgentState,
    )
    from subagents.prompts import (
        INVESTIGATOR_SYSTEM_PROMPT,
        PLANNER_SYSTEM_PROMPT,
        EXECUTOR_SYSTEM_PROMPT,
        VERIFIER_SYSTEM_PROMPT,
        REPORTER_SYSTEM_PROMPT,
        ROGIUS_SYSTEM_PROMPT,
    )
    from subagents.llm_client import call_llm
    from subagents.investigator import InvestigatorAgent
    from subagents.planner import PlannerAgent
    from subagents.executor import ExecutorAgent
    from subagents.verifier import VerifierAgent
    from subagents.reporter import ReporterAgent
    from subagents.main import RogiusMainAgent, run_agentic_workflow
    from subagents.renamer import RenamerAgent
    
    # RAG Tools
    from tools.rag_search import RAGSearchClient, RAGResult, rag_search
    from tools.rag_indexer import ProjectIndexer, IndexConfig, index_project

__all__ = [
    # Enums
    "StepStatus",
    "PlanStatus",
    "AgentPhase",
    "VerificationResult",
    "FailureHint",
    # Models
    "PlanStep",
    "EnvironmentContext",
    "AgentState",
    # Functions
    "call_llm",
    "run_agentic_workflow",
    # System prompts
    "INVESTIGATOR_SYSTEM_PROMPT",
    "PLANNER_SYSTEM_PROMPT",
    "EXECUTOR_SYSTEM_PROMPT",
    "VERIFIER_SYSTEM_PROMPT",
    "REPORTER_SYSTEM_PROMPT",
    "ROGIUS_SYSTEM_PROMPT",
    # Agents
    "InvestigatorAgent",
    "PlannerAgent",
    "ExecutorAgent",
    "VerifierAgent",
    "ReporterAgent",
    "RogiusMainAgent",
    "RenamerAgent",
    # RAG Tools
    "RAGSearchClient",
    "RAGResult",
    "rag_search",
    "ProjectIndexer",
    "IndexConfig",
    "index_project",
]
