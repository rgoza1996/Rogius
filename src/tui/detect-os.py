#!/usr/bin/env python3
"""
OS Detection Script

Detects the operating system and selects the appropriate shell.
Can be run standalone to verify detection is working correctly.
"""

import sys
from pathlib import Path

# Ensure imports work
sys.path.insert(0, str(Path(__file__).parent))

from launcher import OSDetector, OperatingSystem, print_detection_results
from shell_runner import ShellRunner


def test_shell_command():
    """Test running a command in the detected shell."""
    print("\n" + "=" * 50)
    print("SHELL COMMAND TEST")
    print("=" * 50)
    
    runner = ShellRunner()
    print(f"Selected shell: {runner.shell_config.name}")
    print(f"Executable: {runner.shell_config.executable}")
    print("-" * 50)
    
    # Run a simple test command
    if runner.shell_config.name == "PowerShell":
        test_cmd = "Write-Output 'Hello from PowerShell!'; Get-Date"
    else:
        test_cmd = "echo 'Hello from Bash!' && date"
    
    print(f"Running: {test_cmd}")
    result = runner.run(test_cmd)
    
    print(f"\nExit code: {result.exit_code}")
    print(f"Output:\n{result.stdout}")
    
    if result.stderr:
        print(f"Errors:\n{result.stderr}")
    
    # Test file operations
    print("\n" + "=" * 50)
    print("FILE OPERATION TEST")
    print("=" * 50)
    
    test_file = Path.home() / ".rogius_test_file.txt"
    
    # Create file
    print(f"Creating file: {test_file}")
    result = runner.create_file(str(test_file), "Hello from Rogius TUI!")
    print(f"Create result: Exit {result.exit_code}")
    if result.exit_code == 0:
        print("✓ File created successfully")
        
        # Read file
        result = runner.read_file(str(test_file))
        print(f"\nRead result: Exit {result.exit_code}")
        print(f"Content: {result.stdout}")
        
        # Delete file
        result = runner.delete_file(str(test_file))
        print(f"\nDelete result: Exit {result.exit_code}")
        if result.exit_code == 0:
            print("✓ File deleted successfully")
    else:
        print(f"✗ Failed to create file: {result.stderr}")
    
    print("\n" + "=" * 50)


def main():
    """Main function."""
    print_detection_results()
    test_shell_command()
    
    print("\nOS Detection and Shell Selection Complete!")
    print(f"This system will use: {OSDetector.get_shell_config().name}")


if __name__ == "__main__":
    main()
