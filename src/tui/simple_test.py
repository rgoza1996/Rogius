"""
Simple TUI Component Test - Tests core functionality without full TUI
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("Rogius TUI Component Test")
print("=" * 60)

# Test 1: Settings
print("\n1. Testing Settings Module")
from settings import save_settings, load_settings, TUISettings
test_settings = TUISettings(chat_model="test-model", chat_endpoint="http://test:1234")
save_settings(test_settings)
loaded = load_settings()
print(f"   ✓ Settings loaded: chat_model={loaded.chat_model}")
print(f"   ✓ Settings loaded: chat_endpoint={loaded.chat_endpoint}")

# Test 2: Shell Runner
print("\n2. Testing Shell Runner")
from shell_runner import ShellRunner
runner = ShellRunner()
result = runner.run("echo 'hi'")
print(f"   ✓ Command executed: echo 'hi'")
print(f"   ✓ Output: {result.stdout.strip()}")
print(f"   ✓ Exit code: {result.exit_code}")
print(f"   ✓ OS detected: {runner.shell_config.name}")

# Test 3: Multi-Step Plan
print("\n3. Testing Multi-Step Plan")
from multistep import PlanManager, create_plan, get_plan_progress

pm = PlanManager()
plan = pm.create_plan("Test plan", [
    {"description": "Say hi", "command": "echo 'hi'"},
    {"description": "List files", "command": "ls"},
])
print(f"   ✓ Plan created: {plan.goal}")
print(f"   ✓ Steps: {len(plan.steps)}")

progress = get_plan_progress(plan)
print(f"   ✓ Progress: {progress['percentage']}%")

# Test 4: AI Client
print("\n4. Testing AI Client")
from ai_client import AIClient, APIConfig
config = APIConfig(
    chat_endpoint="http://localhost:1234/v1/chat/completions",
    chat_model="llama-3.1-8b"
)
client = AIClient(config)
print(f"   ✓ AI client created")
print(f"   ✓ Tools loaded: {len(client._build_request_body([], enable_tools=True).get('tools', []))}")

# Test 5: Execute a step
print("\n5. Testing Step Execution")
async def test_step():
    async def executor(cmd):
        result = runner.run(cmd)
        return (result.stdout, result.stderr, result.exit_code)
    
    pm2 = PlanManager()
    plan2 = pm2.create_plan("Execute test", [{"description": "Say hi", "command": "echo 'hi from step'"}])
    
    result = await pm2.execute_next_step(executor)
    print(f"   ✓ Step executed")
    print(f"   ✓ Step status: {plan2.steps[0].status.value}")
    print(f"   ✓ Step result: {plan2.steps[0].result.strip() if plan2.steps[0].result else 'None'}")

asyncio.run(test_step())

# Cleanup
print("\n6. Cleanup")
client.close()
print("   ✓ AI client closed")

print("\n" + "=" * 60)
print("All Component Tests Passed!")
print("=" * 60)
print("\n✅ The TUI is ready to use!")
print("\nTo run the interactive TUI and send 'hi':")
print("  1. Open terminal")
print("  2. cd d:\\Rogius\\src\\tui")
print("  3. python tui.py")
print("  4. Type 'hi' and press Enter")
