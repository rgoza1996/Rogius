"""
Terminal Tool - Shell command execution for Rogius.

Encapsulates all terminal-specific logic including:
- Cross-platform command execution (PowerShell/Bash)
- Failure classification and fix application
- File creation verification
"""

import re
import os
from typing import Optional
from .tool_interface import Tool, Action, ActionType, ToolResult
from .tool_registry import tool

# Import from tui - these may not be available during initial import
# so we handle ImportError gracefully
try:
    from ..tui.shell_runner import ShellRunner, CommandResult
    from ..tui.launcher import OSDetector, OperatingSystem, ShellConfig
except ImportError:
    # Fallback for when running from tools folder directly
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from tui.shell_runner import ShellRunner, CommandResult
    from tui.launcher import OSDetector, OperatingSystem, ShellConfig


@tool(ActionType.TERMINAL_COMMAND)
class TerminalTool(Tool):
    """
    Tool for executing terminal commands across platforms.
    
    Handles PowerShell on Windows and Bash on Linux/macOS.
    Provides failure classification and automatic fix application.
    """
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.TERMINAL_COMMAND
    
    async def execute(self, action: Action, env_context: dict) -> ToolResult:
        """
        Execute a terminal command.
        
        Args:
            action: Action with payload containing 'command', optional 'cwd'
            env_context: Dict with 'os_type', 'shell', 'working_directory'
            
        Returns:
            ToolResult with stdout, stderr, exit_code in artifacts
        """
        payload = action.payload
        command = payload.get("command", "")
        cwd = payload.get("cwd") or env_context.get("working_directory")
        timeout = payload.get("timeout", action.timeout)
        
        if not command:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error="No command specified in action payload"
            )
        
        # Get shell configuration based on OS
        os_type = env_context.get("os_type", "windows")
        try:
            shell_config = OSDetector.get_shell_config(OperatingSystem(os_type))
        except (ValueError, KeyError):
            # Default to PowerShell on Windows, Bash otherwise
            if os_type == "windows":
                shell_config = ShellConfig(
                    name="PowerShell",
                    executable="powershell.exe",
                    shell_args=["-Command"]
                )
            else:
                shell_config = ShellConfig(
                    name="Bash",
                    executable="/bin/bash",
                    shell_args=["-c"]
                )
        
        # Create runner and execute
        runner = ShellRunner(shell_config=shell_config, cwd=cwd)
        result = runner.run(command, timeout=timeout)
        
        # Build ToolResult
        success = result.exit_code == 0
        output = result.stdout if success else (result.stderr or f"Exit code: {result.exit_code}")
        
        return ToolResult(
            success=success,
            output=output[:500] if output else "(no output)",
            artifacts={
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_code,
                "command": result.command,
                "shell_used": result.shell_used
            },
            error=result.stderr if not success else None
        )
    
    def verify(self, action: Action, result: ToolResult) -> dict:
        """
        Terminal-specific verification.
        
        Checks exit code and classifies failures.
        Also verifies file creation operations actually created files.
        
        Returns:
            Dict with verification data including exit_code, failure_hint, file_created
        """
        artifacts = result.artifacts
        exit_code = artifacts.get("exit_code", 1)
        stderr = artifacts.get("stderr", "")
        command = action.payload.get("command", "")
        
        # Check if this is a file creation operation
        file_path = self._extract_file_path(command)
        file_verification = None
        
        if file_path and result.success:
            # File should have been created - verify it exists
            file_exists = self._verify_file_exists(file_path)
            if not file_exists:
                # File creation failed despite exit code 0
                result.success = False
                result.error = f"File not created at expected path: {file_path}"
                exit_code = 1
                file_verification = {"path": file_path, "exists": False, "reason": "not_created"}
            else:
                file_verification = {"path": file_path, "exists": True}
        
        # Classify failure
        failure_hint = self._classify_failure(stderr, exit_code)
        
        verification_data = {
            "tool_verified": result.success,
            "exit_code": exit_code,
            "failure_hint": failure_hint,
            "file_created": file_verification
        }
        
        return verification_data
    
    def apply_failure_fix(self, action: Action, hint: str) -> Optional[Action]:
        """
        Apply terminal-specific fixes based on failure hint.
        
        Args:
            action: The failed Action
            hint: The failure hint string
            
        Returns:
            Modified Action with fixed command, or None if no fix available
        """
        command = action.payload.get("command", "")
        if not command:
            return None
        
        fixed_command = None
        
        if hint == "missing_binary":
            fixed_command = self._fix_missing_binary(command)
        elif hint == "permission_denied":
            fixed_command = self._fix_permission_denied(command)
        elif hint == "wrong_cwd":
            fixed_command = self._fix_wrong_cwd(command)
        elif hint == "missing_env_var":
            fixed_command = self._fix_missing_env_var(command)
        elif hint == "timeout":
            fixed_command = self._fix_timeout(command)
        elif hint == "host_unreachable":
            fixed_command = self._fix_host_unreachable(command)
        elif hint == "invalid_arguments":
            fixed_command = self._fix_invalid_arguments(command)
        elif hint == "missing_dependency":
            fixed_command = self._fix_missing_dependency(command)
        
        if fixed_command:
            # Create new action with fixed command
            new_payload = action.payload.copy()
            new_payload["command"] = fixed_command
            return Action(
                type=action.type,
                payload=new_payload,
                description=f"{action.description} (retry with fix: {hint})",
                timeout=action.timeout
            )
        
        return None
    
    def classify_failure(self, result: ToolResult) -> str:
        """Classify failure from ToolResult."""
        artifacts = result.artifacts
        stderr = artifacts.get("stderr", "")
        exit_code = artifacts.get("exit_code", 1)
        return self._classify_failure(stderr, exit_code)
    
    # -------------------------------------------------------------------------
    # Helper methods (moved from Executor and Verifier agents)
    # -------------------------------------------------------------------------
    
    def _classify_failure(self, stderr: str, exit_code: int) -> str:
        """Classify terminal failures based on stderr and exit code."""
        if exit_code == 0:
            return "none"
        
        stderr_lower = stderr.lower() if stderr else ""
        
        if "command not found" in stderr_lower or "not recognized" in stderr_lower or "'" in stderr_lower and "is not recognized" in stderr_lower:
            return "missing_binary"
        elif "permission denied" in stderr_lower or "access denied" in stderr_lower:
            return "permission_denied"
        elif "no such file" in stderr_lower or "cannot find" in stderr_lower or "does not exist" in stderr_lower:
            return "wrong_cwd"
        elif "timeout" in stderr_lower or "timed out" in stderr_lower or exit_code == 124:
            return "timeout"
        elif "connection refused" in stderr_lower or "host is down" in stderr_lower or "unreachable" in stderr_lower:
            return "host_unreachable"
        elif "invalid" in stderr_lower or "unrecognized" in stderr_lower or "unknown option" in stderr_lower:
            return "invalid_arguments"
        elif "module not found" in stderr_lower or "package not found" in stderr_lower or "cannot find module" in stderr_lower:
            return "missing_dependency"
        elif "environment variable" in stderr_lower or "$" in stderr_lower and "not set" in stderr_lower:
            return "missing_env_var"
        
        return "unknown"
    
    def _extract_file_path(self, command: str) -> Optional[str]:
        """Extract file path from command for file creation operations."""
        if not command:
            return None
        
        # Check if this looks like a file creation command
        command_lower = command.lower()
        is_file_creation = any(keyword in command_lower for keyword in [
            "new-item", "set-content", "out-file", "add-content",
            "> ", ">> ", "touch ", "echo ", "cat >", "cat >>",
            "writefile", "writefile", "writefile"
        ])
        
        if not is_file_creation:
            return None
        
        # Pattern matching for file paths
        patterns = [
            # PowerShell patterns
            r'-Path\s+["\']([^"\']+)["\']',
            r'-FilePath\s+["\']([^"\']+)["\']',
            r'-Destination\s+["\']([^"\']+)["\']',
            r'New-Item\s+(?:-ItemType\s+File\s+)?(?:-Path\s+)?["\']([^"\']+)["\']',
            r'Set-Content\s+["\']([^"\']+)["\']',
            r'Out-File\s+(?:-FilePath\s+)?["\']([^"\']+)["\']',
            # Bash redirect patterns
            r'(?:>|>>)\s*["\']([^"\']+\.[a-zA-Z0-9]+)["\']',
            r'(?:>|>>)\s+([a-zA-Z]?:?\\?[^\s"\']+[^\s"\']*\.\w+)',
            # touch, echo patterns
            r'touch\s+["\']?([^"\']+)["\']?',
            r'echo\s+.*>\s*["\']?([^"\']+)["\']?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                path = match.group(1)
                # Verify it looks like a file path (has extension or path separator)
                if '.' in path or '/' in path or '\\' in path:
                    return path
        
        return None
    
    def _verify_file_exists(self, file_path: str) -> bool:
        """Verify that a file actually exists on the filesystem."""
        try:
            # Normalize Windows paths
            if '\\' in file_path or ':' in file_path:
                normalized_path = os.path.normpath(file_path)
            else:
                # Unix paths with possible ~ expansion
                if file_path.startswith('~'):
                    file_path = os.path.expanduser(file_path)
                normalized_path = file_path
            
            exists = os.path.exists(normalized_path) and os.path.isfile(normalized_path)
            return exists
        except Exception:
            return False
    
    def _fix_missing_binary(self, command: str) -> Optional[str]:
        """Try alternative binary names."""
        if not command:
            return None
        
        parts = command.split()
        if not parts:
            return None
        
        binary = parts[0]
        rest = ' '.join(parts[1:]) if len(parts) > 1 else ""
        
        # Common alternative names
        alternatives = {
            "python": ["python3", "python3.11", "python3.10", "/usr/bin/python3"],
            "pip": ["pip3", "python3 -m pip", "/usr/bin/pip3"],
            "node": ["nodejs", "/usr/bin/node"],
            "npm": ["/usr/bin/npm"],
            "docker": ["/usr/bin/docker"],
            "kubectl": ["oc", "/usr/local/bin/kubectl"],
            "ssh": ["/usr/bin/ssh", "/usr/local/bin/ssh"],
            "git": ["/usr/bin/git", "/usr/local/bin/git"],
            "code": ["/usr/bin/code", "/usr/local/bin/code"],
        }
        
        if binary in alternatives:
            for alt in alternatives[binary]:
                if rest:
                    return f"{alt} {rest}"
                return alt
        
        # Try which command on Unix
        if '/' not in binary and '\\' not in binary:
            return f"$(which {binary} 2>/dev/null || echo '{binary}') {rest}"
        
        return None
    
    def _fix_permission_denied(self, command: str) -> Optional[str]:
        """Add elevated privileges."""
        if not command:
            return None
        
        # Check if it looks like a Windows command
        if any(windows_cmd in command.lower() for windows_cmd in ['powershell', 'get-', 'set-', 'new-item']):
            # PowerShell elevation attempt
            return f'powershell -Command "Start-Process {command} -Verb runAs"'
        else:
            # Unix sudo
            return f"sudo {command}"
    
    def _fix_wrong_cwd(self, command: str) -> Optional[str]:
        """Try from home directory."""
        if not command:
            return None
        
        # Check if it looks like a Windows command
        if any(windows_cmd in command.lower() for windows_cmd in ['powershell', 'get-', 'set-']):
            return f"cd %USERPROFILE% && {command}"
        else:
            return f"cd ~ && {command}"
    
    def _fix_missing_env_var(self, command: str) -> Optional[str]:
        """Set common missing environment variables."""
        if not command:
            return None
        
        if "HOME" in command or "~" in command:
            # Set HOME if missing
            if any(windows_cmd in command.lower() for windows_cmd in ['powershell', 'get-', 'set-']):
                return f'set HOME=%USERPROFILE% && {command}'
            else:
                return f'export HOME=${{HOME:-~}} && {command}'
        
        # Add common paths to PATH
        if any(windows_cmd in command.lower() for windows_cmd in ['powershell', 'get-', 'set-']):
            return f'set PATH=%PATH%;C:\\Windows\\System32 && {command}'
        else:
            return f'export PATH="$PATH:/usr/local/bin:/usr/bin" && {command}'
    
    def _fix_timeout(self, command: str) -> Optional[str]:
        """Add timeout handling."""
        if not command:
            return None
        
        # Add nohang for Unix
        if 'powershell' not in command.lower():
            return f"timeout 300 {command} || true"
        return None
    
    def _fix_host_unreachable(self, command: str) -> Optional[str]:
        """Add connection timeout and retry options."""
        if not command:
            return None
        
        if "ssh" in command.lower():
            # Add SSH connection options
            return command.replace("ssh ", "ssh -o ConnectTimeout=30 -o ConnectionAttempts=3 ", 1)
        
        return None
    
    def _fix_invalid_arguments(self, command: str) -> Optional[str]:
        """Strip problematic flags."""
        if not command:
            return None
        
        # Remove common problematic flags
        simplified = command
        for flag in ["--color", "-v", "--verbose", "--progress", "-i", "--interactive", "--fancy", "--pretty"]:
            simplified = simplified.replace(f" {flag}", "").replace(f"{flag} ", "")
        
        return simplified if simplified != command else None
    
    def _fix_missing_dependency(self, command: str) -> Optional[str]:
        """Try to install missing dependency."""
        if not command:
            return None
        
        # Try to install common dependencies
        if "npm" in command.lower() or "node" in command.lower():
            return f"npm install && {command}"
        elif "pip" in command.lower() or "python" in command.lower():
            # Extract package name from command
            parts = command.split()
            if len(parts) > 1:
                pkg = parts[-1]
                return f"pip install {pkg} && {command}"
        
        return None

    def get_schema(self) -> dict:
        """
        Return schema for terminal_command action.
        """
        return {
            "type": "terminal_command",
            "description": "Execute shell commands across platforms (PowerShell on Windows, Bash on Linux/macOS)",
            "payload_schema": {
                "command": "The exact terminal command to execute",
                "cwd": "Optional working directory (relative to project root)"
            },
            "os_specific_syntax": {
                "windows": "Use PowerShell syntax: Get-ChildItem, New-Item, Test-Path, etc.",
                "linux": "Use Bash syntax: ls, mkdir, test, etc.",
                "macos": "Use Bash syntax: ls, mkdir, test, etc."
            },
            "failure_hints": [
                "missing_binary: Command not in PATH",
                "permission_denied: Access denied, need elevated privileges",
                "wrong_cwd: Working directory incorrect",
                "missing_env_var: Required environment variable not set",
                "invalid_arguments: Arguments malformed or incompatible with OS",
                "host_unreachable: SSH/network connection failed",
                "timeout: Command timed out",
                "missing_dependency: Required tool/library not installed"
            ]
        }
    
    def get_examples(self) -> list[dict]:
        """
        Return example terminal_command actions.
        """
        return [
            {
                "payload": {
                    "command": "New-Item -Path 'file.txt' -ItemType File -Value 'Hello World'"
                },
                "description": "Create a file with content (Windows)",
                "timeout": 30
            },
            {
                "payload": {
                    "command": "echo 'Hello World' > file.txt"
                },
                "description": "Create a file with content (Linux/macOS)",
                "timeout": 30
            },
            {
                "payload": {
                    "command": "Get-ChildItem -Path . -Recurse -File"
                },
                "description": "List all files recursively (Windows)",
                "timeout": 60
            },
            {
                "payload": {
                    "command": "find . -type f"
                },
                "description": "List all files recursively (Linux/macOS)",
                "timeout": 60
            },
            {
                "payload": {
                    "command": "Test-Path 'file.txt'"
                },
                "description": "Check if file exists (Windows)",
                "timeout": 10
            },
            {
                "payload": {
                    "command": "test -f file.txt"
                },
                "description": "Check if file exists (Linux/macOS)",
                "timeout": 10
            },
            {
                "payload": {
                    "command": "Remove-Item -Path 'file.txt' -Force"
                },
                "description": "Delete a file (Windows)",
                "timeout": 30
            },
            {
                "payload": {
                    "command": "rm file.txt"
                },
                "description": "Delete a file (Linux/macOS)",
                "timeout": 30
            }
        ]


# Make TerminalTool available for import
__all__ = ["TerminalTool"]
