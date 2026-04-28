"""
Automated TUI Test - Simulates user interaction
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from tui import RogiusTUI
from textual.app import App

async def test_tui():
    """Test TUI functionality programmatically."""
    print("=" * 60)
    print("Rogius TUI Automated Test")
    print("=" * 60)
    
    # Create app instance (without running the full TUI)
    app = RogiusTUI()
    
    print("\n1. Testing Component Initialization")
    print(f"   - Shell runner: {app.shell_runner.shell_config.name}")
    print(f"   - Settings loaded: {app.settings.chat_model}")
    print(f"   - AI client: {'Ready' if app.ai_client else 'None'}")
    print(f"   - Plan manager: {'Ready' if app.plan_manager else 'None'}")
    
    print("\n2. Testing Message Handling")
    # Simulate adding messages
    app.messages = []
    app.add_message("user", "hi")
    print(f"   - Added user message 'hi'")
    print(f"   - Message count: {len(app.messages)}")
    
    app.add_message("assistant", "Hello! I'm Rogius. How can I help you today?")
    print(f"   - Added assistant response")
    print(f"   - Message count: {len(app.messages)}")
    
    print("\n3. Testing Slash Commands")
    
    # Test /help
    print("   - Testing /help command...")
    try:
        app.handle_slash_command("/help")
        print("   - /help executed successfully")
    except Exception as e:
        print(f"   - /help error: {e}")
    
    # Test /pwd
    print("   - Testing /pwd command...")
    try:
        app.handle_slash_command("/pwd")
        print(f"   - Current dir: {app.shell_runner.cwd}")
    except Exception as e:
        print(f"   - /pwd error: {e}")
    
    # Test /plan
    print("   - Testing /plan command...")
    try:
        app.handle_slash_command('/plan Test plan [{"description": "Step 1", "command": "echo hello"}]')
        if app.plan_manager.active_plan:
            print(f"   - Plan created: {app.plan_manager.active_plan.goal}")
            print(f"   - Steps: {len(app.plan_manager.active_plan.steps)}")
        else:
            print("   - No plan created")
    except Exception as e:
        print(f"   - /plan error: {e}")
    
    print("\n4. Testing Multi-Step Execution")
    if app.plan_manager.active_plan:
        async def mock_executor(cmd):
            return (f"Executed: {cmd}", "", 0)
        
        try:
            result = await app.plan_manager.execute_next_step(mock_executor)
            print(f"   - Step executed successfully")
            print(f"   - Current step index: {app.plan_manager.active_plan.current_step_index}")
        except Exception as e:
            print(f"   - Step execution error: {e}")
    
    print("\n5. Testing Terminal Commands")
    try:
        result = app.shell_runner.run("echo 'hi from TUI'")
        print(f"   - Command executed: echo 'hi from TUI'")
        print(f"   - Output: {result.stdout.strip()}")
        print(f"   - Exit code: {result.exit_code}")
    except Exception as e:
        print(f"   - Command error: {e}")
    
    print("\n6. Testing Settings Persistence")
    from settings import save_settings, load_settings, TUISettings
    test_settings = TUISettings(chat_model="test-model")
    save_settings(test_settings)
    loaded = load_settings()
    print(f"   - Settings saved and loaded")
    print(f"   - Chat model: {loaded.chat_model}")
    
    print("\n" + "=" * 60)
    print("TUI Test Complete!")
    print("=" * 60)
    print("\nTo run the interactive TUI:")
    print("  cd d:\\Rogius\\src\\tui")
    print("  python tui.py")
    print("\nThen type 'hi' and press Enter")
    
    # Cleanup
    await app.ai_client.close()

if __name__ == "__main__":
    asyncio.run(test_tui())
