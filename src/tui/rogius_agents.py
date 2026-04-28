"""
Rogius Multi-Agent System (Legacy Import Proxy)

This file has been refactored. The actual implementations have been moved to the `subagents` package.
This file is kept for backwards compatibility.
"""

import sys
from pathlib import Path

# Add parent dir to path if needed so subagents can be found
_this_dir = Path(__file__).parent
_src_dir = _this_dir.parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from subagents.models import *
from subagents.prompts import *
from subagents.llm_client import *
from subagents.investigator import InvestigatorAgent
from subagents.planner import PlannerAgent
from subagents.executor import ExecutorAgent
from subagents.verifier import VerifierAgent
from subagents.reporter import ReporterAgent
from subagents.main import RogiusMainAgent, run_agentic_workflow
