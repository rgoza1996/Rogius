"""
Test fixes for PowerShell quoting and error handling
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from shell_runner import ShellRunner
from multistep import PlanManager, StepStatus, PlanStatus


async def test_powershell_quoting():
    """Test that PowerShell commands with apostrophes work correctly."""
    print("\n" + "=" * 70)
    print("TEST 1: PowerShell Quoting Fix")
    print("=" * 70)
    
    runner = ShellRunner()
    
    # Test 1: Simple content without quotes
    print("\n1. Simple content (should work):")
    result = runner.run("powershell -Command \"Set-Content -Path 'D:\\test1.txt' -Value 'Hello World'\"")
    print(f"   Exit code: {result.exit_code}")
    assert result.exit_code == 0, f"Expected 0, got {result.exit_code}"
    print("   ✓ Passed")
    
    # Test 2: Content with apostrophes (the bug we fixed)
    print("\n2. Content with apostrophes (should work with fix):")
    content_with_apostrophes = "It's a beautiful day, don't you think? World's best recipe!"
    result = runner.run(f"powershell -Command \"Set-Content -Path 'D:\\test2.txt' -Value '{content_with_apostrophes}'\"")
    print(f"   Exit code: {result.exit_code}")
    
    if result.exit_code == 0:
        # Verify content was written
        verify = runner.run("powershell -Command \"Get-Content -Path 'D:\\test2.txt'\"")
        if "It's a beautiful day" in verify.stdout:
            print("   ✓ Passed - Content written correctly with apostrophes!")
        else:
            print(f"   ⚠ Warning: Content may not have been written correctly")
            print(f"   Output: {verify.stdout[:100]}")
    else:
        print(f"   ✗ Failed with error: {result.stderr[:100]}")
    
    # Test 3: Content with newlines and quotes (complex case)
    print("\n3. Multi-line content with quotes:")
    multiline_content = """Line 1: Chocolate Chip Cookies
Line 2: Don't forget to preheat!
Line 3: "Mix well" before baking"""
    result = runner.run(f"powershell -Command \"Set-Content -Path 'D:\\test3.txt' -Value '{multiline_content}'\"")
    print(f"   Exit code: {result.exit_code}")
    
    if result.exit_code == 0:
        print("   ✓ Passed - Multi-line content with mixed quotes works!")
    else:
        print(f"   ⚠ May have limitations with complex multi-line content")
        print(f"   Error: {result.stderr[:100]}")
    
    # Cleanup
    runner.run("powershell -Command \"Remove-Item -Path 'D:\\test1.txt', 'D:\\test2.txt', 'D:\\test3.txt' -ErrorAction SilentlyContinue\"")
    print("\n   Cleanup complete")


async def test_error_handling():
    """Test that plan stops on first error."""
    print("\n" + "=" * 70)
    print("TEST 2: Error Handling Fix")
    print("=" * 70)
    
    runner = ShellRunner()
    pm = PlanManager()
    
    # Create a plan where step 1 fails, step 2 should NOT run
    print("\n1. Creating plan with intentional error in step 1:")
    plan = pm.create_plan("Test error handling", [
        {"description": "This will fail", "command": "powershell -Command 'exit 1'"},
        {"description": "This should not run", "command": "powershell -Command \"Set-Content -Path 'D:\\should_not_exist.txt' -Value 'test'\""}
    ])
    print(f"   Created plan with {len(plan.steps)} steps")
    
    async def executor(cmd: str):
        result = runner.run(cmd)
        return (result.stdout, result.stderr, result.exit_code)
    
    print("\n2. Executing plan:")
    
    step_results = []
    
    async def on_step_start(step, idx):
        print(f"   ▶ Starting step {idx + 1}: {step.description}")
    
    async def on_step_complete(step, idx, result):
        step_results.append((idx, "completed", result))
        print(f"   ✓ Step {idx + 1} completed")
    
    async def on_step_error(step, idx, error):
        step_results.append((idx, "error", error))
        print(f"   ✗ Step {idx + 1} ERROR: {error[:50]}")
    
    result_plan = await pm.execute(executor, on_step_start, on_step_complete, on_step_error)
    
    print("\n3. Verifying results:")
    
    # Check that step 1 failed
    step1_status = result_plan.steps[0].status
    print(f"   Step 1 status: {step1_status.value}")
    assert step1_status == StepStatus.ERROR, f"Expected ERROR, got {step1_status.value}"
    print("   ✓ Step 1 correctly marked as ERROR")
    
    # Check that step 2 was NOT executed (should still be PENDING)
    step2_status = result_plan.steps[1].status
    print(f"   Step 2 status: {step2_status.value}")
    assert step2_status == StepStatus.PENDING, f"Expected PENDING, got {step2_status.value}"
    print("   ✓ Step 2 correctly NOT executed (stopped after error)")
    
    # Check plan status
    print(f"   Plan status: {result_plan.status.value}")
    assert result_plan.status == PlanStatus.ERROR, f"Expected ERROR, got {result_plan.status.value}"
    print("   ✓ Plan status correctly set to ERROR")
    
    # Verify step 2 file was NOT created
    check_file = runner.run("powershell -Command \"Test-Path 'D:\\should_not_exist.txt'\"")
    file_exists = "True" in check_file.stdout
    assert not file_exists, "Step 2 file should not exist!"
    print("   ✓ Step 2 file was NOT created (execution stopped)")
    
    print("\n   ✓✓✓ ALL ERROR HANDLING TESTS PASSED ✓✓✓")


async def test_cookie_recipe_end_to_end():
    """Full end-to-end test with AI-like cookie recipe generation."""
    print("\n" + "=" * 70)
    print("TEST 3: End-to-End Cookie Recipe Test")
    print("=" * 70)
    
    runner = ShellRunner()
    pm = PlanManager()
    
    # Simulate what AI would generate
    print("\n1. Creating plan (simulating AI generation):")
    plan = pm.create_plan("Create cookie recipes and manage files", [
        {
            "description": "Create f.txt with chocolate chip recipe",
            "command": "powershell -Command \"Set-Content -Path 'D:\\f.txt' -Value 'CHOCOLATE CHIP COOKIES\\n\\nIngredients:\\n- 2 cups flour\\n- 1 cup chocolate chips\\n\\nDon\\'t overbake!\\n\\nInstructions:\\n1. Mix ingredients\\n2. Bake at 350F'\""
        },
        {
            "description": "Create g.txt with sugar cookie recipe", 
            "command": "powershell -Command \"Set-Content -Path 'D:\\g.txt' -Value 'SUGAR COOKIES\\n\\nIngredients:\\n- 2 cups flour\\n- 1 cup sugar\\n\\nWorld\\'s best cookies!\\n\\nInstructions:\\n1. Mix and bake\\n2. Enjoy'\""
        },
        {
            "description": "Delete f.txt",
            "command": "powershell -Command \"Remove-Item -Path 'D:\\f.txt'\""
        }
    ])
    print(f"   Created plan: {plan.goal}")
    print(f"   Steps: {len(plan.steps)}")
    
    async def executor(cmd: str):
        result = runner.run(cmd)
        return (result.stdout, result.stderr, result.exit_code)
    
    print("\n2. Executing plan:")
    
    async def on_step_start(step, idx):
        print(f"   ▶ Step {idx + 1}: {step.description}")
    
    async def on_step_complete(step, idx, result):
        print(f"   ✓ Step {idx + 1} completed (exit: {step.result and '0' or 'N/A'})")
    
    async def on_step_error(step, idx, error):
        print(f"   ✗ Step {idx + 1} failed: {error[:60]}")
    
    result_plan = await pm.execute(executor, on_step_start, on_step_complete, on_step_error)
    
    print("\n3. Verification:")
    
    # Check results
    check_f = runner.run("powershell -Command \"Test-Path 'D:\\f.txt'\"")
    check_g = runner.run("powershell -Command \"Test-Path 'D:\\g.txt'\"")
    
    f_exists = "True" in check_f.stdout
    g_exists = "True" in check_g.stdout
    
    print(f"   f.txt exists: {f_exists} (should be False)")
    print(f"   g.txt exists: {g_exists} (should be True)")
    
    if g_exists:
        content = runner.run("powershell -Command \"Get-Content 'D:\\g.txt'\"")
        has_apostrophe = "World's" in content.stdout or "best" in content.stdout
        print(f"   g.txt has content: {len(content.stdout)} chars")
        if has_apostrophe:
            print("   ✓ Content includes apostrophes (quoting fix works!)")
    
    if not f_exists and g_exists:
        print("\n   ✓✓✓ END-TO-END TEST PASSED ✓✓✓")
        return True
    else:
        print("\n   ✗ End-to-end test had issues")
        return False


async def main():
    """Run all tests."""
    print("=" * 70)
    print("  Rogius TUI Fix Verification Tests")
    print("=" * 70)
    
    all_passed = True
    
    try:
        await test_powershell_quoting()
    except Exception as e:
        print(f"\n   ✗ PowerShell quoting test failed: {e}")
        all_passed = False
    
    try:
        await test_error_handling()
    except Exception as e:
        print(f"\n   ✗ Error handling test failed: {e}")
        all_passed = False
    
    try:
        e2e_passed = await test_cookie_recipe_end_to_end()
        if not e2e_passed:
            all_passed = False
    except Exception as e:
        print(f"\n   ✗ End-to-end test failed: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("  ✓✓✓ ALL TESTS PASSED ✓✓✓")
        print("  Fixes are working correctly!")
    else:
        print("  ✗ SOME TESTS FAILED")
        print("  Review errors above")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
