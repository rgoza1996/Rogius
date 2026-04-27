"""
Investigator Agent

Agent 1: The Scout - Probes the environment to gather context before planning.
"""

import json
import sys
from typing import Optional, Callable
from pathlib import Path

# Handle imports for both package and direct execution
try:
    from .models import AgentState, AgentPhase, EnvironmentContext
    from .prompts import INVESTIGATOR_SYSTEM_PROMPT
    from ..tui.launcher import OSDetector, OperatingSystem, ShellConfig
    from ..tui.shell_runner import ShellRunner
    from ..tui.settings import TUISettings
    from ..tools.web_search import web_search
    from ..tools.rag_search import rag_search, RAGSearchClient
except ImportError:
    _src_dir = Path(__file__).parent.parent
    if str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))
    from subagents.models import AgentState, AgentPhase, EnvironmentContext
    from subagents.prompts import INVESTIGATOR_SYSTEM_PROMPT
    from tui.launcher import OSDetector, OperatingSystem, ShellConfig
    from tui.shell_runner import ShellRunner
    from tui.settings import TUISettings
    from tools.web_search import web_search
    from tools.rag_search import rag_search, RAGSearchClient


class InvestigatorAgent:
    """
    Agent 1: The Scout
    Probes the environment to gather context before planning.
    """

    async def run(self, state: AgentState, llm_call: Callable, event_callback: Optional[Callable] = None) -> AgentState:
        """
        Execute investigation phase.

        Args:
            state: Current agent state
            llm_call: Function to call LLM
            event_callback: Optional callback to emit events (for streaming)

        Returns:
            Updated state with environment_context populated
        """
        print(f"[Investigator] Starting investigation for goal: {state.user_goal[:50]}...")

        state.phase = AgentPhase.INVESTIGATING

        # First, detect OS using native Python (always reliable)
        os_type = OSDetector.detect()
        shell_config = OSDetector.get_shell_config(os_type)
        system_info = OSDetector.get_system_info()

        # Build investigation prompt
        prompt = f"""
User Goal: {state.user_goal}

Detected OS: {os_type.value}
Default Shell: {shell_config.name}

Generate investigation commands to gather context for this goal.
Consider:
- What files/directories might already exist?
- What tools/commands might be needed?
- What environment variables might be relevant?
"""

        # Emit prompt event if callback provided
        if event_callback:
            await event_callback({
                'type': 'agent_prompt',
                'agent': 'Investigator',
                'system_prompt': INVESTIGATOR_SYSTEM_PROMPT,
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
                        'agent': 'Investigator',
                        'chunk': chunk
                    })

            # Get LLM to suggest investigation commands with streaming
            response = await llm_call(
                system_prompt=INVESTIGATOR_SYSTEM_PROMPT,
                user_prompt=prompt,
                expected_schema=dict,  # {commands: [], rationale: str}
                stream_callback=stream_chunk
            )

            # Emit final inference event with complete response
            if event_callback:
                await event_callback({
                    'type': 'agent_inference',
                    'agent': 'Investigator',
                    'response': json.dumps(response, indent=2)
                })

            suggested_commands = response.get("commands", [])
            web_search_queries = response.get("web_search_queries", [])
            rag_search_queries = response.get("rag_search_queries", [])

            # Auto-detect RAG keywords if no explicit queries
            if not rag_search_queries:
                rag_keywords = ["this project", "our codebase", "workspace", "project files", 
                               "the code", "this file", "find in project", "search files"]
                for keyword in rag_keywords:
                    if keyword in state.user_goal.lower():
                        rag_search_queries = [state.user_goal]
                        break

            # Execute RAG searches if requested or auto-detected
            rag_results = []
            if rag_search_queries:
                print(f"[Investigator] Performing {len(rag_search_queries)} RAG search(es)...")
                
                # Load settings for RAG configuration
                settings = TUISettings()
                rag_client = RAGSearchClient(
                    embedding_model=settings.rag_embedding_model,
                    embedding_endpoint=settings.rag_embedding_endpoint,
                    api_type=settings.rag_api_type
                )
                
                for query in rag_search_queries:
                    try:
                        search_result = await rag_client.search(query, top_k=5)
                        rag_results.append({
                            "query": query,
                            "results": [
                                {
                                    "content": r.content,
                                    "source": r.source,
                                    "score": r.score,
                                    "metadata": r.metadata
                                } for r in search_result
                            ]
                        })
                        print(f"[Investigator] RAG searched: '{query[:50]}...' " + (f"✓ ({len(search_result)} results)" if search_result else "✗"))
                    except Exception as e:
                        rag_results.append({
                            "query": query,
                            "error": str(e)
                        })
                        print(f"[Investigator] RAG search failed for '{query}': {e}")

            # Execute web searches if requested
            web_search_results = []
            if web_search_queries:
                print(f"[Investigator] Performing {len(web_search_queries)} web search(es)...")
                for query in web_search_queries:
                    try:
                        search_result = await web_search(query, max_results=5)
                        web_search_results.append({
                            "query": query,
                            "results": search_result
                        })
                        print(f"[Investigator] Searched: '{query[:50]}...' " + ("✓" if search_result else "✗"))
                    except Exception as e:
                        web_search_results.append({
                            "query": query,
                            "error": str(e)
                        })
                        print(f"[Investigator] Web search failed for '{query}': {e}")

            # Execute the suggested commands
            runner = ShellRunner(shell_config=shell_config)
            investigation_results = []

            # Always include basic context commands
            basic_commands = []
            if os_type == OperatingSystem.WINDOWS:
                basic_commands = [
                    "whoami",
                    "$PWD",
                    "Get-ChildItem -Path . -Name | Select-Object -First 20"
                ]
            else:
                basic_commands = [
                    "whoami",
                    "pwd",
                    "ls -la | head -20"
                ]

            all_commands = basic_commands + suggested_commands

            for cmd in all_commands:
                try:
                    result = runner.run(cmd, timeout=10)
                    investigation_results.append({
                        "command": cmd,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "exit_code": result.exit_code
                    })
                except Exception as e:
                    investigation_results.append({
                        "command": cmd,
                        "error": str(e)
                    })

            # Build environment context
            state.environment_context = EnvironmentContext(
                os_type=os_type.value,
                os_name=system_info.get("os", "unknown"),
                shell=shell_config.name,
                working_directory=runner.cwd,
                username=system_info.get("username", ""),
                hostname=system_info.get("hostname", ""),
                available_commands=self._extract_available_commands(investigation_results),
                relevant_files=self._extract_relevant_files(investigation_results, state.user_goal),
                environment_variables={},
                web_search_results=web_search_results,
                rag_search_results=rag_results
            )

            # Record in history
            state.execution_history.append({
                "phase": "investigation",
                "commands_run": len(all_commands),
                "web_searches": len(web_search_results),
                "rag_searches": len(rag_results),
                "os_detected": os_type.value,
                "shell": shell_config.name
            })

            print(f"[Investigator] Complete. OS: {os_type.value}, Shell: {shell_config.name}")

        except Exception as e:
            # Fallback to basic context if LLM call fails
            state.environment_context = EnvironmentContext(
                os_type=os_type.value,
                os_name=system_info.get("os", "unknown"),
                shell=shell_config.name,
                working_directory=system_info.get("working_directory", str(Path.cwd())),
                username=system_info.get("username", ""),
                hostname=system_info.get("hostname", ""),
                web_search_results=[]
            )
            state.execution_history.append({
                "phase": "investigation",
                "error": str(e),
                "fallback": True
            })
            print(f"[Investigator] Warning: LLM call failed, using fallback context: {e}")

        return state

    def _extract_available_commands(self, results: list[dict]) -> list[str]:
        """Extract available commands from investigation results."""
        commands = []
        for r in results:
            if "which" in r.get("command", "") or "Get-Command" in r.get("command", ""):
                if r.get("exit_code") == 0:
                    stdout = r.get("stdout", "")
                    commands.extend([c.strip() for c in stdout.split("\n") if c.strip()])
        return commands[:10]  # Limit to first 10

    def _extract_relevant_files(self, results: list[dict], goal: str) -> list[str]:
        """Extract files relevant to the goal from investigation results."""
        files = []
        keywords = [k.lower() for k in goal.split() if len(k) > 3]

        for r in results:
            if "ls" in r.get("command", "") or "Get-ChildItem" in r.get("command", ""):
                if r.get("exit_code") == 0:
                    stdout = r.get("stdout", "")
                    for line in stdout.split("\n"):
                        line_lower = line.lower()
                        if any(k in line_lower for k in keywords):
                            files.append(line.strip())

        return files[:10]
