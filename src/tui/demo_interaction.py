"""
TUI Demo - Shows message interaction without full TUI
This demonstrates what happens when you send "hi" to the TUI
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from shell_runner import ShellRunner
from multistep import PlanManager, create_plan
from ai_client import AIClient, APIConfig, ChatMessage
from settings import TUISettings

print("=" * 70)
print("  Rogius TUI - Simulated User Interaction")
print("=" * 70)

# Initialize components
settings = TUISettings()
runner = ShellRunner()
pm = PlanManager()

print("\n🖥️  TUI Components Initialized:")
print(f"   • Shell: {runner.shell_config.name}")
print(f"   • Working directory: {runner.cwd}")
print(f"   • AI Model: {settings.chat_model}")
print(f"   • Multi-step: Ready")

print("\n" + "─" * 70)
print("💬 USER: hi")
print("─" * 70)

# Simulate what the TUI does when receiving "hi"
print("\n📨 Processing message...")

# Add to conversation
conversation = [
    ChatMessage(role="system", content="You are Rogius, an AI assistant."),
    ChatMessage(role="user", content="hi")
]

print("\n🤖 AI Response:")
print("   ┌" + "─" * 66 + "┐")

# Since we can't connect to actual API, show what would happen
demo_response = """Hello! I'm Rogius, your AI assistant with terminal integration.

I can help you with:
• 💬 General questions and chat
• 🖥️ Terminal commands (prefix with $)
• 📋 Multi-step tasks (use /plan)

Try these commands:
  $ dir              - List directory contents  
  $ echo hello       - Say hello
  /plan test         - Create a multi-step plan
  /help              - Show all commands

What would you like to do?"""

for line in demo_response.split('\n'):
    print(f"   │ {line:<64} │")

print("   └" + "─" * 66 + "┘")

print("\n" + "─" * 70)
print("📝 Message added to conversation history")

# Show terminal panel state
print("\n🖥️  Terminal Panel:")
print("   [No commands executed yet]")

# Show plan widget state  
print("\n📋 Plan Widget:")
print("   No active plan")
print("   Create one with: /plan <goal>")

print("\n" + "=" * 70)
print("✅ Demo Complete! The TUI is ready to use.")
print("=" * 70)
print("\nTo use the real TUI:")
print("   cd d:\\Rogius\\src\\tui")
print("   python tui.py")
print("\nThen type your messages and press Enter!")
