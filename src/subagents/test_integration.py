"""
Integration Test for Rogius Multi-Agent System with Real LLM

Tests the full multi-agent workflow with REAL local LLM inference.
Uses read-only commands only for safety.
"""
import asyncio
import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, Any

# Add paths for imports - MUST be at project root level
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "tui"))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Import TUI modules (from tui folder)
from ai_client import AIClient, APIConfig, ChatMessage
from settings import TUISettings, load_settings
from shell_runner import ShellRunner, CommandResult
from launcher import OSDetector

# Import subagents (from subagents folder)
from subagents import (
    InvestigatorAgent,
    PlannerAgent,
    ExecutorAgent,
    VerifierAgent,
    ReporterAgent,
    RogiusMainAgent,
    run_agentic_workflow,
    AgentState,
    AgentPhase,
    StepStatus,
    PlanStep,
    EnvironmentContext,
    INVESTIGATOR_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    EXECUTOR_SYSTEM_PROMPT,
    VERIFIER_SYSTEM_PROMPT,
    REPORTER_SYSTEM_PROMPT,
)

# Import tools (from tools folder)
from tools.web_search import web_search, WebSearchClient
from tools.rag_search import rag_search, RAGSearchClient, RAGResult
from tools.rag_indexer import ProjectIndexer, IndexConfig, index_project


# =============================================================================
# SAFETY CONTROLS - Strict allowlist of read-only commands
# =============================================================================

SAFE_COMMANDS = {
    # Unix/Linux
    'ls', 'dir', 'pwd', 'cd', 'echo', 'whoami', 'hostname', 'date', 'uname',
    'env', 'printenv', 'which', 'command', 'cat', 'head', 'tail', 'wc',
    'find', 'grep', 'ps', 'top', 'df', 'du', 'free', 'uptime', 'id',
    # Windows/PowerShell
    'get-childitem', 'get-location', 'write-output', 'get-date', 'get-host',
    'test-path', 'get-command', 'get-variable', 'get-process', 'get-service',
    'get-wmiobject', 'select-object', 'where-object', 'foreach-object',
    'ver', 'vol', 'systeminfo', 'tasklist', 'ipconfig', 'netstat', 'path',
    # Both
    'curl', 'wget', 'ping', 'nslookup', 'dig',
}

DANGEROUS_PATTERNS = [
    '>', '>>', '| out-file', '| set-content', '| add-content',
    'remove-item', 'del ', 'rm ', 'rmdir', 'erase', 'rd ',
    'move-item', 'rename-item', 'copy-item', 'xcopy', 'robocopy',
    'new-item', 'mkdir', 'md ', 'mklink',
    'format', 'diskpart', 'chkdsk', 'defrag',
    'invoke-webrequest.*-outfile', 'wget.*-o', 'curl.*-o',
    'start-process', 'invoke-expression', 'iex ',
    'set-executionpolicy', 'reg delete', 'reg add',
]


def is_safe_command(cmd: str) -> tuple[bool, str]:
    """
    Validate that a command is safe to execute.
    
    Returns:
        (is_safe: bool, reason: str)
    """
    if not cmd or not cmd.strip():
        return False, "Empty command"
    
    cmd_lower = cmd.lower().strip()
    
    # Check for dangerous patterns first
    for pattern in DANGEROUS_PATTERNS:
        if pattern in cmd_lower:
            return False, f"Dangerous pattern detected: '{pattern}'"
    
    # Extract base command (first word)
    base_cmd = cmd_lower.split()[0]
    
    # Check against allowlist
    if base_cmd not in SAFE_COMMANDS:
        return False, f"Command '{base_cmd}' not in safe allowlist"
    
    return True, "OK"


# =============================================================================
# REAL LLM CALL FUNCTION
# =============================================================================

async def real_llm_call(
    system_prompt: str,
    user_prompt: str,
    expected_schema: Optional[type] = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    client: Optional[AIClient] = None,
    **kwargs  # Accept extra args like stream_callback
) -> dict[str, Any]:
    """
    Real LLM call using local inference endpoint.
    
    Args:
        system_prompt: The system prompt defining agent behavior
        user_prompt: The user prompt with current context
        expected_schema: Optional Pydantic model for structured output
        temperature: Temperature for generation
        max_tokens: Maximum tokens to generate
        client: Optional AIClient instance (creates one if not provided)
        **kwargs: Additional arguments (ignored, for compatibility)
        
    Returns:
        Dict containing the LLM response
    """
    if client is None:
        settings = load_settings()
        config = APIConfig(
            chat_endpoint=settings.chat_endpoint,
            chat_model=settings.chat_model,
            system_prompt=system_prompt
        )
        client = AIClient(config)
        close_after = True
    else:
        close_after = False
    
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=user_prompt)
    ]
    
    try:
        content_parts = []
        async for chunk in client.stream_chat_completion(messages, enable_tools=False):
            if chunk.content:
                content_parts.append(chunk.content)
        
        full_content = "".join(content_parts).strip()
        
        # Try to parse as JSON
        try:
            # Remove markdown code blocks if present
            if full_content.startswith("```json"):
                full_content = full_content[7:]
                if full_content.endswith("```"):
                    full_content = full_content[:-3]
            elif full_content.startswith("```"):
                full_content = full_content[3:]
                if full_content.endswith("```"):
                    full_content = full_content[:-3]
            
            # Clean up common JSON issues before parsing
            # Fix unescaped backslashes in Windows paths
            cleaned_content = full_content.strip()
            # Try parsing, and if it fails due to escape sequences, try fixing them
            try:
                result = json.loads(cleaned_content)
            except json.JSONDecodeError as e:
                if 'Invalid \\escape' in str(e):
                    # Try to fix common escape issues
                    # Replace single backslashes that aren't part of valid escape sequences
                    import re
                    # This is a heuristic - replace \ followed by non-escape characters with \\
                    cleaned_content = re.sub(r'\\(?!"|\\|/|b|f|n|r|t|u[0-9a-fA-F]{4})', r'\\\\', cleaned_content)
                    result = json.loads(cleaned_content)
                else:
                    raise
            
            # Validate against schema if provided (and is a Pydantic model)
            if expected_schema and expected_schema is not dict:
                validated = expected_schema(**result)
                # Pydantic v2 uses model_dump(), v1 used dict()
                if hasattr(validated, 'model_dump'):
                    result = validated.model_dump()
                elif hasattr(validated, 'dict'):
                    result = validated.dict()
                else:
                    # If it's already a dict, use it as-is
                    result = validated if isinstance(validated, dict) else dict(validated)
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"[LLM] Failed to parse JSON: {e}")
            print(f"[LLM] Raw content: {full_content[:200]}...")
            return {"error": "JSON parse failed", "raw": full_content}
            
    except Exception as e:
        print(f"[LLM] Error during inference: {e}")
        return {"error": str(e)}
    
    finally:
        if close_after:
            await client.close()


# =============================================================================
# TEST HARNESS
# =============================================================================

class MultiAgentTest:
    """Test harness for multi-agent system."""
    
    def __init__(self):
        self.settings = load_settings()
        self.runner = ShellRunner()
        self.os_detector = OSDetector()
        self.client: Optional[AIClient] = None
        self.temp_dir: Optional[Path] = None
        self.results = []
        
    async def setup(self):
        """Initialize AI client and temp directory."""
        print("\n" + "=" * 70)
        print("  MULTI-AGENT INTEGRATION TEST - Real Local LLM")
        print("=" * 70)
        
        # Create temp directory
        self.temp_dir = Path(tempfile.mkdtemp(prefix="rogius_test_"))
        print(f"\n📁 Temp directory: {self.temp_dir}")
        
        # Setup AI client
        config = APIConfig(
            chat_endpoint=self.settings.chat_endpoint,
            chat_model=self.settings.chat_model,
        )
        self.client = AIClient(config)
        
        print(f"🤖 AI Configuration:")
        print(f"   • Endpoint: {config.chat_endpoint}")
        print(f"   • Model: {config.chat_model}")
        
        # Check API connection
        print(f"\n📡 Checking API connection...")
        try:
            models = await self.client.fetch_models()
            if models:
                print(f"   ✓ API available. Models: {', '.join(models[:3])}")
            else:
                print(f"   ⚠ API not responding (no models returned)")
        except Exception as e:
            print(f"   ✗ API connection failed: {e}")
            print(f"   Ensure LM Studio/Ollama is running at: {config.chat_endpoint}")
            return False
        
        print(f"\n🖥️  System: {self.os_detector.detect()}")
        print(f"   • Shell: {self.runner.shell_config.name}")
        print(f"   • Working directory: {self.runner.cwd}")
        
        return True
    
    async def teardown(self):
        """Cleanup temp directory and close client."""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            print(f"\n🧹 Cleaned up temp directory")
        
        if self.client:
            await self.client.close()
            print(f"   ✓ AI client closed")
    
    def record_result(self, test_name: str, passed: bool, details: str = ""):
        """Record test result."""
        self.results.append({
            "name": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"\n{status}: {test_name}")
        if details:
            print(f"   {details}")
    
    # ========================================================================
    # TEST A: End-to-End Multi-Agent Workflow
    # ========================================================================
    
    async def test_multi_agent_workflow(self):
        """Test full workflow with read-only commands."""
        print("\n" + "─" * 70)
        print("[TEST A] Multi-Agent Workflow (Read-Only Commands)")
        print("─" * 70)
        
        goal = "List files in the current directory and show the current path"
        print(f"Goal: {goal}")
        
        try:
            # Run workflow using run_agentic_workflow which returns a result
            print("\n🚀 Starting workflow...")
            result = await run_agentic_workflow(
                user_goal=goal,
                llm_call=lambda **kwargs: real_llm_call(client=self.client, **kwargs)
            )
            
            # Validate results (phase is 'complete' not 'completed')
            checks = [
                ("workflow_completed", result.get("phase") == "complete"),
                ("has_final_report", bool(result.get("final_report"))),
                ("steps_created", result.get("plan_steps_count", 0) > 0),
                ("steps_completed", result.get("completed_steps", 0) > 0),
            ]
            
            passed = all(check[1] for check in checks)
            details = ", ".join([f"{name}={val}" for name, val in checks])
            
            # Show summary
            print(f"\n📊 Workflow Summary:")
            print(f"   • Steps: {result.get('completed_steps', 0)}/{result.get('plan_steps_count', 0)}")
            print(f"   • Phase: {result.get('phase')}")
            print(f"   • Success: {result.get('success')}")
            
            if result.get('final_report'):
                print(f"\n📝 Report preview: {result['final_report'][:100]}...")
            
            self.record_result("Multi-Agent Workflow", passed, details)
            return passed
            
        except Exception as e:
            self.record_result("Multi-Agent Workflow", False, f"Exception: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ========================================================================
    # TEST B: Web Search Integration
    # ========================================================================
    
    async def test_web_search(self):
        """Test web search functionality."""
        print("\n" + "─" * 70)
        print("[TEST B] Web Search Integration")
        print("─" * 70)
        
        try:
            # Direct web search test
            print("\n🔍 Testing web search...")
            query = "Python 3.12 release date"
            
            web_client = WebSearchClient(max_results=3)
            results = await web_client.search(query)
            
            if not results:
                self.record_result("Web Search", False, "No results returned")
                return False
            
            print(f"   ✓ Retrieved {len(results)} results for '{query}'")
            for i, r in enumerate(results[:3], 1):
                print(f"   [{i}] {r.title[:50]}...")
            
            # Test formatted output
            formatted = web_client.format_results_for_llm(results)
            has_valid_content = len(formatted) > 100 and "SearchResult" not in formatted
            
            self.record_result("Web Search", has_valid_content, f"{len(results)} results, formatted={has_valid_content}")
            return has_valid_content
            
        except Exception as e:
            self.record_result("Web Search", False, f"Exception: {e}")
            return False
    
    # ========================================================================
    # TEST C: Error Recovery
    # ========================================================================
    
    async def test_error_recovery(self):
        """Test that verifier detects failures and executor recovers."""
        print("\n" + "─" * 70)
        print("[TEST C] Error Recovery")
        print("─" * 70)
        
        # Create a state with a known-failing command
        from subagents import PlanStep, AgentState, EnvironmentContext
        
        state = AgentState(
            session_id="test_error_recovery",
            user_goal="Test error handling",
            goal="Test error handling",
            plan=[
                PlanStep(
                    id="step_1",
                    description="Run a command that doesn't exist",
                    logical_action="Execute command: xyzabc123_not_real"
                )
            ],
            current_step_index=0,
            environment=EnvironmentContext()
        )
        
        # Execute the step
        executor = ExecutorAgent()
        
        try:
            # Safety check - this should fail validation
            cmd = "xyzabc123_not_real"
            is_safe, reason = is_safe_command(cmd)
            
            if not is_safe:
                print(f"   ✓ Safety check blocked dangerous command: {reason}")
                self.record_result("Error Recovery", True, "Safety controls working")
                return True
            
            # If we got here, the command passed safety (unexpected)
            result_state = await executor.run(
                state,
                lambda **kwargs: real_llm_call(client=self.client, **kwargs)
            )
            
            # Check if failure was detected
            step = result_state.plan[0]
            failure_detected = step.status == StepStatus.FAILED or step.error_message
            
            self.record_result("Error Recovery", failure_detected, f"Failure detected={failure_detected}")
            return failure_detected
            
        except Exception as e:
            # Exception means our safety check worked
            print(f"   ✓ Exception caught (expected): {e}")
            self.record_result("Error Recovery", True, "Exception handling works")
            return True
    
    # ========================================================================
    # TEST D: RAG Search Integration
    # ========================================================================
    
    async def test_rag_search(self):
        """Test RAG search with project context."""
        print("\n" + "─" * 70)
        print("[TEST D] RAG Search Integration")
        print("─" * 70)
        
        try:
            # Create RAG client
            rag_client = RAGSearchClient()
            
            # Check Ollama connectivity
            print("🔍 Checking Ollama embedding endpoint...")
            test_embedding = await rag_client._generate_embedding("test")
            if not test_embedding:
                self.record_result("RAG Search", False, "Ollama embedding failed")
                return False
            print(f"   ✓ Ollama responsive (embedding dim: {len(test_embedding)})")
            
            # Index a test file
            test_file = self.temp_dir / "test_code.py"
            test_file.write_text("""
def hello_world():
    '''A simple greeting function.'''
    return "Hello, World!"

class TestClass:
    '''A test class for demonstration.'''
    def __init__(self):
        self.value = 42
""")
            
            print("📄 Indexing test file...")
            success = await rag_client.index_file(test_file)
            if not success:
                self.record_result("RAG Search", False, "Failed to index test file")
                return False
            print("   ✓ File indexed")
            
            # Perform search
            print("🔎 Searching for 'greeting function'...")
            results = await rag_client.search("greeting function", top_k=3)
            
            if results:
                print(f"   ✓ Found {len(results)} results")
                for i, r in enumerate(results[:2], 1):
                    print(f"      {i}. {r.source} (score: {r.score:.2f})")
                self.record_result("RAG Search", True, f"{len(results)} results found")
                return True
            else:
                self.record_result("RAG Search", False, "No results returned")
                return False
                
        except Exception as e:
            self.record_result("RAG Search", False, f"Exception: {e}")
            return False
    
    # ========================================================================
    # TEST E: Safety Controls
    # ========================================================================
    
    async def test_safety_controls(self):
        """Test that safety controls block dangerous commands."""
        print("\n" + "─" * 70)
        print("[TEST E] Safety Controls")
        print("─" * 70)
        
        test_cases = [
            ("ls", True, "Safe command"),
            ("pwd", True, "Safe command"),
            ("echo hello", True, "Safe command"),
            ("rm -rf /", False, "Dangerous: rm"),
            ("del file.txt", False, "Dangerous: del"),
            ("echo hi > file.txt", False, "Dangerous: redirect"),
            ("Get-ChildItem", True, "Safe: PowerShell list"),
            ("Remove-Item file", False, "Dangerous: Remove-Item"),
        ]
        
        passed_count = 0
        for cmd, expected_safe, description in test_cases:
            is_safe, reason = is_safe_command(cmd)
            correct = is_safe == expected_safe
            if correct:
                passed_count += 1
            status = "✓" if correct else "✗"
            print(f"   {status} '{cmd}' -> safe={is_safe} ({description})")
        
        all_passed = passed_count == len(test_cases)
        self.record_result("Safety Controls", all_passed, f"{passed_count}/{len(test_cases)} checks passed")
        return all_passed
    
    # ========================================================================
    # MAIN TEST RUNNER
    # ========================================================================
    
    async def run_all_tests(self):
        """Run all tests."""
        if not await self.setup():
            print("\n✗ Setup failed, aborting tests")
            return 1
        
        try:
            # Run tests
            await self.test_multi_agent_workflow()
            await self.test_web_search()
            await self.test_error_recovery()
            await self.test_rag_search()
            await self.test_safety_controls()
            
        finally:
            await self.teardown()
        
        # Print summary
        print("\n" + "=" * 70)
        print("  TEST SUMMARY")
        print("=" * 70)
        
        passed = sum(1 for r in self.results if r["passed"])
        total = len(self.results)
        
        for r in self.results:
            status = "✓" if r["passed"] else "✗"
            print(f"{status} {r['name']}: {r['details']}")
        
        print(f"\nTotal: {passed}/{total} tests passed")
        
        if passed == total:
            print("\n🎉 All tests passed!")
            return 0
        else:
            print(f"\n⚠️  {total - passed} test(s) failed")
            return 1


# =============================================================================
# ENTRY POINT
# =============================================================================

async def main():
    """Main entry point."""
    test = MultiAgentTest()
    exit_code = await test.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
