"""
Real AI Test - Connects to actual LLM and executes generated plan
"""
import asyncio
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from shell_runner import ShellRunner
from multistep import PlanManager, create_plan, get_plan_progress, StepStatus
from ai_client import AIClient, APIConfig, ChatMessage, ConversationManager
from settings import TUISettings


async def run_real_ai_test():
    """Run test with actual AI inference."""
    print("=" * 70)
    print("  REAL AI TEST - Rogius TUI with Live LLM")
    print("=" * 70)
    
    # Initialize
    settings = TUISettings()
    runner = ShellRunner()
    pm = PlanManager()
    
    print("\n🖥️  TUI Components Initialized")
    print(f"   • Shell: {runner.shell_config.name}")
    print(f"   • Working directory: {runner.cwd}")
    
    # Setup AI client
    config = APIConfig(
        chat_endpoint=settings.chat_endpoint,  # http://localhost:1234/v1/chat/completions
        chat_model=settings.chat_model,
        system_prompt="""You are Rogius, an AI assistant that helps with file operations.
When the user asks for multi-step tasks, you MUST use the start_multistep_task tool.
Break down complex tasks into executable steps using PowerShell commands."""
    )
    
    client = AIClient(config)
    conversation = ConversationManager(config.system_prompt)
    
    print(f"\n🤖 AI Configuration:")
    print(f"   • Endpoint: {config.chat_endpoint}")
    print(f"   • Model: {config.chat_model}")
    
    # Check if API is available
    print("\n📡 Checking API connection...")
    models = await client.fetch_models()
    if models:
        print(f"   ✓ API available. Models: {', '.join(models[:3])}")
    else:
        print(f"   ⚠ API not responding. Ensure LM Studio/Ollama is running.")
        print(f"   Expected at: {config.chat_endpoint}")
        await client.close()
        return
    
    # User prompt
    user_prompt = (
        "Create two files in D:\\ drive: f.txt and g.txt, "
        "put detailed cookie recipes in both files, then delete f.txt. "
        "Use PowerShell commands. Make sure the recipes include ingredients and instructions."
    )
    
    print("\n" + "─" * 70)
    print(f"💬 SENDING PROMPT TO AI:")
    print(f"   {user_prompt}")
    print("─" * 70)
    
    conversation.add_user_message(user_prompt)
    
    # Stream AI response
    print("\n🤖 AI RESPONSE (streaming):")
    print("   ", end="", flush=True)
    
    assistant_content = ""
    pending_tool_calls = []
    
    try:
        async for chunk in client.stream_chat_completion(
            conversation.get_messages(),
            enable_tools=True
        ):
            if chunk.content:
                content = str(chunk.content).replace("[object Object]", "")
                assistant_content += content
                print(content, end="", flush=True)
            
            if chunk.tool_calls:
                pending_tool_calls.extend(chunk.tool_calls)
        
        print()  # New line after streaming
        
        # Handle tool calls
        if pending_tool_calls:
            print(f"\n🔧 AI REQUESTED {len(pending_tool_calls)} TOOL CALL(S)")
            
            for tc in pending_tool_calls:
                tool_name = tc.function_name
                if not tool_name:
                    continue
                
                print(f"\n   Tool: {tool_name}")
                
                try:
                    args = json.loads(tc.function_arguments) if tc.function_arguments else {}
                except json.JSONDecodeError:
                    args = {}
                
                print(f"   Arguments: {json.dumps(args, indent=6)}")
                
                # Execute the tool
                if tool_name == "start_multistep_task":
                    goal = args.get("goal", "Task")
                    steps = args.get("steps", [])
                    
                    plan = pm.create_plan(goal, steps)
                    print(f"\n📋 PLAN CREATED BY AI:")
                    print(f"   Goal: {plan.goal}")
                    print(f"   Steps: {len(plan.steps)}")
                    for i, step in enumerate(plan.steps, 1):
                        print(f"   {i}. {step.description}")
                    
                    # Now execute the plan
                    print("\n🔄 EXECUTING AI-GENERATED PLAN:")
                    
                    async def powershell_executor(cmd: str) -> tuple[str, str, int]:
                        print(f"   Executing: {cmd[:60]}...")
                        result = runner.run(cmd)
                        return (result.stdout, result.stderr, result.exit_code)
                    
                    async def on_step_start(step, idx):
                        print(f"\n   ▶ Step {idx + 1}: {step.description}")
                    
                    async def on_step_complete(step, idx, result):
                        status = "✓" if step.status.value == "completed" else "✗"
                        print(f"     {status} Step completed successfully")
                    
                    async def on_step_error(step, idx, error):
                        print(f"     ✗ Error: {error[:50]}")
                    
                    # Execute all steps
                    completed_plan = await pm.execute(
                        powershell_executor,
                        on_step_start,
                        on_step_complete,
                        on_step_error
                    )
                    
                    # Show final progress
                    progress = get_plan_progress(completed_plan)
                    print(f"\n📊 FINAL PROGRESS:")
                    print(f"   Completed: {progress['completed']}/{progress['total']} steps")
                    print(f"   Percentage: {progress['percentage']}%")
                    print(f"   Status: {completed_plan.status.value}")
                    
                elif tool_name == "execute_command":
                    command = args.get("command", "")
                    if command:
                        print(f"   Executing command directly...")
                        result = runner.run(command)
                        print(f"   Exit code: {result.exit_code}")
                        print(f"   Output: {result.stdout[:100] if result.stdout else '(none)'}")
        else:
            print("\n⚠ AI did not request any tools. Response was text-only:")
            print(f"   {assistant_content[:200]}...")
        
        conversation.add_assistant_message(assistant_content)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Verification
    print("\n" + "=" * 70)
    print("✅ VERIFICATION:")
    print("=" * 70)
    
    check_f = runner.run("powershell -Command \"Test-Path 'D:\\f.txt'\"")
    check_g = runner.run("powershell -Command \"Test-Path 'D:\\g.txt'\"")
    
    f_exists = "True" in check_f.stdout
    g_exists = "True" in check_g.stdout
    
    print(f"   f.txt exists: {f_exists} (should be False - deleted)")
    print(f"   g.txt exists: {g_exists} (should be True - kept)")
    
    if g_exists:
        content = runner.run("powershell -Command \"Get-Content 'D:\\g.txt' -TotalCount 5\"")
        print(f"\n   g.txt content preview:")
        for line in content.stdout.strip().split('\n')[:5]:
            print(f"     {line}")
    
    if not f_exists and g_exists:
        print("\n🎉 SUCCESS: AI correctly created and managed files!")
    else:
        print("\n⚠️  Check file states manually")
    
    await client.close()
    print("\n🏁 Test complete.")


if __name__ == "__main__":
    asyncio.run(run_real_ai_test())
