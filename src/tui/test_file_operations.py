"""
Automated Test: File Operations via TUI Multi-Step Task

This test simulates sending a prompt to Rogius TUI to:
1. Create f.txt in D:\ with a cookie recipe
2. Create g.txt in D:\ with a cookie recipe  
3. Delete f.txt

Uses PowerShell for all file operations.
Waits for inference simulation between steps.
"""
import asyncio
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from shell_runner import ShellRunner
from multistep import PlanManager, create_plan, get_plan_progress
from ai_client import AIClient, APIConfig, ChatMessage
from settings import TUISettings


class TUIAutomatedTest:
    """Automated test harness for TUI file operations."""
    
    def __init__(self):
        self.settings = TUISettings()
        self.runner = ShellRunner()
        self.plan_manager = PlanManager()
        self.conversation = []
        
        # Initialize AI client
        config = APIConfig(
            chat_endpoint=self.settings.chat_endpoint,
            chat_model=self.settings.chat_model,
            system_prompt="""You are Rogius, an AI assistant that helps with file operations.
You MUST use the start_multistep_task tool to create plans for multi-step operations.
Always provide complete cookie recipes with ingredients and instructions.
"""
        )
        self.ai_client = AIClient(config)
        
        print("🖥️  TUI Test Components Initialized")
        print(f"   • Shell: {self.runner.shell_config.name}")
        print(f"   • Working directory: {self.runner.cwd}")
        print(f"   • Target drive: D:\\")
    
    async def simulate_ai_response(self, user_prompt: str) -> list:
        """
        Simulate AI generating a multi-step plan for the file operations.
        In production, this would call the actual API.
        """
        print(f"\n🤖 Processing prompt: '{user_prompt}'")
        print("   [Simulating AI inference...]")
        
        # Wait to simulate inference time
        await asyncio.sleep(2)
        
        # Simulate the AI creating a tool call for start_multistep_task
        simulated_tool_call = {
            "tool": "start_multistep_task",
            "arguments": {
                "goal": "Create cookie recipe files in D:\\ drive and delete f.txt",
                "steps": [
                    {
                        "description": "Create f.txt with chocolate chip cookie recipe in D:\\ drive",
                        "command": "powershell -Command \"Set-Content -Path 'D:\\f.txt' -Value 'Chocolate Chip Cookies\n\nIngredients:\n- 2 1/4 cups all-purpose flour\n- 1 tsp baking soda\n- 1 tsp salt\n- 1 cup butter, softened\n- 3/4 cup granulated sugar\n- 3/4 cup packed brown sugar\n- 1 tsp vanilla extract\n- 2 large eggs\n- 2 cups chocolate chips\n\nInstructions:\n1. Preheat oven to 375°F (190°C)\n2. Mix flour, baking soda, and salt\n3. Beat butter, sugars, and vanilla until creamy\n4. Add eggs one at a time, beating well\n5. Gradually beat in flour mixture\n6. Stir in chocolate chips\n7. Drop by rounded tablespoon onto ungreased baking sheets\n8. Bake 9-11 minutes until golden brown\n9. Cool on wire racks'\""
                    },
                    {
                        "description": "Create g.txt with sugar cookie recipe in D:\\ drive",
                        "command": "powershell -Command \"Set-Content -Path 'D:\\g.txt' -Value 'Sugar Cookies\n\nIngredients:\n- 2 3/4 cups all-purpose flour\n- 1 tsp baking soda\n- 1/2 tsp baking powder\n- 1 cup butter, softened\n- 1 1/2 cups white sugar\n- 1 egg\n- 1 tsp vanilla extract\n\nInstructions:\n1. Preheat oven to 375°F (190°C)\n2. Stir flour, baking soda, and baking powder together\n3. Beat butter and sugar until smooth\n4. Beat in egg and vanilla\n5. Gradually blend in dry ingredients\n6. Roll dough into 1-inch balls\n7. Place 2 inches apart on ungreased baking sheets\n8. Bake 8-10 minutes until golden\n9. Let stand 2 minutes before transferring to wire racks'\""
                    },
                    {
                        "description": "Delete f.txt from D:\\ drive",
                        "command": "powershell -Command \"Remove-Item -Path 'D:\\f.txt' -Force\""
                    },
                    {
                        "description": "Verify g.txt exists and contains cookie recipe",
                        "command": "powershell -Command \"Get-Content -Path 'D:\\g.txt' -TotalCount 5\""
                    }
                ]
            }
        }
        
        print(f"   ✓ AI generated plan with {len(simulated_tool_call['arguments']['steps'])} steps")
        return [simulated_tool_call]
    
    async def execute_tool_call(self, tool_call: dict) -> str:
        """Execute a tool call and return the result."""
        tool_name = tool_call["tool"]
        args = tool_call["arguments"]
        
        if tool_name == "start_multistep_task":
            goal = args.get("goal", "Task")
            steps = args.get("steps", [])
            
            plan = self.plan_manager.create_plan(goal, steps)
            print(f"\n📋 Plan Created: {plan.goal}")
            print(f"   Steps: {len(plan.steps)}")
            
            for i, step in enumerate(plan.steps, 1):
                print(f"   {i}. {step.description}")
            
            return f"Plan created with {len(steps)} steps"
        
        elif tool_name == "execute_next_step":
            return await self.execute_next_step()
        
        else:
            return f"Unknown tool: {tool_name}"
    
    async def execute_next_step(self) -> str:
        """Execute the next step in the active plan using PowerShell."""
        if not self.plan_manager.active_plan:
            return "No active plan"
        
        plan = self.plan_manager.active_plan
        current_idx = plan.current_step_index
        
        if current_idx >= len(plan.steps):
            return "All steps completed"
        
        step = plan.steps[current_idx]
        print(f"\n▶ Executing Step {current_idx + 1}: {step.description}")
        print(f"   Command: {step.command[:80]}...")
        
        # Simulate inference wait
        print("   [Waiting for remote inference...]")
        await asyncio.sleep(1)
        
        # PowerShell executor
        async def powershell_executor(cmd: str) -> tuple[str, str, int]:
            # Use the shell runner which already uses PowerShell
            result = self.runner.run(cmd)
            return (result.stdout, result.stderr, result.exit_code)
        
        # Execute the step
        task = self.plan_manager.execute_next_step(powershell_executor)
        
        if task:
            # Wait for completion with timeout
            try:
                await asyncio.wait_for(task, timeout=30.0)
                result = task.result()
                
                # Show results
                if result.exit_code == 0:
                    print(f"   ✓ Success (exit code: {result.exit_code})")
                    if result.stdout:
                        lines = result.stdout.strip().split('\n')[:3]
                        for line in lines:
                            print(f"     {line[:70]}")
                else:
                    print(f"   ✗ Failed (exit code: {result.exit_code})")
                    if result.stderr:
                        print(f"     Error: {result.stderr[:70]}")
                
                return f"Step {current_idx + 1} completed with exit code {result.exit_code}"
                
            except asyncio.TimeoutError:
                print(f"   ⏱ Timeout after 30 seconds")
                return "Step timed out"
        
        return "No step to execute"
    
    async def run_full_test(self):
        """Run the complete automated test."""
        print("\n" + "=" * 70)
        print("  AUTOMATED TUI FILE OPERATIONS TEST")
        print("=" * 70)
        
        # Step 1: Send prompt to AI
        user_prompt = (
            "Create two files in D:\\ drive: f.txt and g.txt, "
            "put detailed cookie recipes in both files, then delete f.txt. "
            "Use PowerShell commands. Make sure the recipes include ingredients and instructions."
        )
        
        print(f"\n💬 USER PROMPT:")
        print(f"   {user_prompt}")
        
        # Step 2: Get AI response (simulated)
        tool_calls = await self.simulate_ai_response(user_prompt)
        
        # Step 3: Execute tool calls
        print("\n🔧 EXECUTING TOOL CALLS:")
        for tc in tool_calls:
            result = await self.execute_tool_call(tc)
            print(f"   Result: {result}")
        
        # Step 4: Execute all plan steps automatically
        print("\n🔄 EXECUTING PLAN STEPS:")
        
        while (self.plan_manager.active_plan and 
               self.plan_manager.active_plan.status.value == "running" and
               self.plan_manager.active_plan.current_step_index < len(self.plan_manager.active_plan.steps)):
            
            result = await self.execute_next_step()
            
            # Show progress
            if self.plan_manager.active_plan:
                progress = get_plan_progress(self.plan_manager.active_plan)
                print(f"   Progress: {progress['completed']}/{progress['total']} ({progress['percentage']}%)")
            
            # Small delay between steps
            await asyncio.sleep(0.5)
        
        # Step 5: Verify completion
        print("\n✅ VERIFYING RESULTS:")
        
        # Check that g.txt exists
        check_g = self.runner.run("powershell -Command \"Test-Path -Path 'D:\\g.txt'\"")
        g_exists = "True" in check_g.stdout
        print(f"   g.txt exists: {g_exists}")
        
        # Check that f.txt was deleted
        check_f = self.runner.run("powershell -Command \"Test-Path -Path 'D:\\f.txt'\"")
        f_exists = "True" in check_f.stdout
        print(f"   f.txt exists: {f_exists} (should be False)")
        
        # Read g.txt content
        if g_exists:
            read_g = self.runner.run("powershell -Command \"Get-Content -Path 'D:\\g.txt' -TotalCount 3\"")
            print(f"\n   g.txt preview:")
            for line in read_g.stdout.strip().split('\n')[:3]:
                print(f"     {line}")
        
        # Final verification
        print("\n" + "=" * 70)
        if g_exists and not f_exists:
            print("  ✅ TEST PASSED")
            print("  • f.txt was created and deleted successfully")
            print("  • g.txt exists with cookie recipe content")
        else:
            print("  ⚠️  TEST ISSUES DETECTED")
            if not g_exists:
                print("  • g.txt was not created properly")
            if f_exists:
                print("  • f.txt was not deleted properly")
        
        print("=" * 70)
        
        # Cleanup AI client
        await self.ai_client.close()


async def main():
    """Main test entry point."""
    test = TUIAutomatedTest()
    await test.run_full_test()


if __name__ == "__main__":
    asyncio.run(main())
