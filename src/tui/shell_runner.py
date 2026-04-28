"""
Cross-Platform Shell Runner

Executes commands in the appropriate shell based on OS.
Handles PowerShell on Windows and Bash on Linux/macOS.
"""

import subprocess
import shlex
import sys
from typing import Optional
from dataclasses import dataclass
from pathlib import Path

from launcher import OSDetector, ShellConfig, OperatingSystem


@dataclass
class CommandResult:
    """Result of a command execution."""
    stdout: str
    stderr: str
    exit_code: int
    command: str
    shell_used: str


class ShellRunner:
    """Runs commands in the appropriate shell for the current OS."""
    
    def __init__(self, shell_config: ShellConfig = None, cwd: str = None):
        """
        Initialize the shell runner.
        
        Args:
            shell_config: Shell configuration. If None, auto-detects from OS.
            cwd: Working directory for command execution.
        """
        self.shell_config = shell_config or OSDetector.get_shell_config()
        self.cwd = cwd or str(Path.cwd())
        self.command_history: list[CommandResult] = []
    
    def _escape_powershell_content(self, content: str) -> str:
        """
        Escape content for safe use in PowerShell Set-Content commands.
        Uses here-string syntax to avoid quote escaping issues.
        """
        # Use PowerShell here-string syntax
        # @'
        # content here (no escaping needed)
        # '@
        return f"@'\n{content}\n'@"
    
    def _needs_powershell_escaping(self, command: str) -> bool:
        """Check if a command needs special PowerShell escaping."""
        # Check for Set-Content with nested quotes/apostrophes
        if "Set-Content" in command and ("'" in command or '"' in command):
            return True
        return False
    
    def _prepare_powershell_command(self, command: str) -> str:
        """Prepare a command for safe PowerShell execution."""
        if not self._needs_powershell_escaping(command):
            return command
        
        # For Set-Content commands, replace the -Value parameter with here-string
        import re
        
        # Pattern to match Set-Content with -Value '...' or -Value "..."
        pattern = r"(Set-Content\s+-Path\s+['\"]([^'\"]+)['\"]\s+-Value\s+)(['\"])(.*?)(\3)"
        match = re.search(pattern, command, re.DOTALL)
        
        if match:
            prefix = match.group(1)
            path = match.group(2)
            content = match.group(4)
            
            # Rebuild with here-string
            return f'Set-Content -Path "{path}" -Value {self._escape_powershell_content(content)}'
        
        return command
    
    def run(self, command: str, timeout: int = 30) -> CommandResult:
        """
        Run a command in the configured shell.
        
        Args:
            command: The command to execute
            timeout: Maximum execution time in seconds
            
        Returns:
            CommandResult with stdout, stderr, exit_code, etc.
        """
        # Prepare command for PowerShell if needed
        if self.shell_config.name == "PowerShell":
            command = self._prepare_powershell_command(command)
        
        # Build the full command with shell arguments
        args = [self.shell_config.executable] + self.shell_config.shell_args + [command]
        
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.cwd,
                encoding='utf-8',
                errors='replace'
            )
            
            cmd_result = CommandResult(
                stdout=result.stdout.strip() if result.stdout else "",
                stderr=result.stderr.strip() if result.stderr else "",
                exit_code=result.returncode,
                command=command,
                shell_used=self.shell_config.name
            )
            
        except subprocess.TimeoutExpired:
            cmd_result = CommandResult(
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                exit_code=124,
                command=command,
                shell_used=self.shell_config.name
            )
        except FileNotFoundError:
            cmd_result = CommandResult(
                stdout="",
                stderr=f"Shell not found: {self.shell_config.executable}",
                exit_code=127,
                command=command,
                shell_used=self.shell_config.name
            )
        except Exception as e:
            cmd_result = CommandResult(
                stdout="",
                stderr=f"Error executing command: {str(e)}",
                exit_code=1,
                command=command,
                shell_used=self.shell_config.name
            )
        
        self.command_history.append(cmd_result)
        return cmd_result
    
    def run_interactive(self, command: str, timeout: int = 30) -> CommandResult:
        """
        Run a command that requires an interactive terminal (TTY).
        Useful for SSH, tailscale ssh, and other interactive commands.
        
        Note: This streams output directly to stdout/stderr and may not
        capture output properly on all platforms. Use run() for non-interactive
        commands that need output capture.
        
        Args:
            command: The command to execute
            timeout: Maximum execution time in seconds
            
        Returns:
            CommandResult (output capture may be limited)
        """
        try:
            # For interactive commands, we need to allocate a pseudo-terminal
            # Use 'script' on Unix or appropriate PTY allocation
            if sys.platform == 'win32':
                # Windows: use start command or conpty if available
                args = ['cmd', '/c', command]
            else:
                # Unix/Linux/macOS: use script to allocate PTY
                args = ['script', '-q', '-c', command, '/dev/null']
            
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.cwd,
                encoding='utf-8',
                errors='replace'
            )
            
            cmd_result = CommandResult(
                stdout=result.stdout.strip() if result.stdout else "",
                stderr=result.stderr.strip() if result.stderr else "",
                exit_code=result.returncode,
                command=command,
                shell_used=self.shell_config.name
            )
            
        except subprocess.TimeoutExpired:
            cmd_result = CommandResult(
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                exit_code=124,
                command=command,
                shell_used=self.shell_config.name
            )
        except FileNotFoundError as e:
            cmd_result = CommandResult(
                stdout="",
                stderr=f"Command not found: {e.filename}",
                exit_code=127,
                command=command,
                shell_used=self.shell_config.name
            )
        except Exception as e:
            cmd_result = CommandResult(
                stdout="",
                stderr=f"Error executing command: {str(e)}",
                exit_code=1,
                command=command,
                shell_used=self.shell_config.name
            )
        
        self.command_history.append(cmd_result)
        return cmd_result
    
    def run_ssh(self, user_host: str, remote_command: str, 
                identity_file: Optional[str] = None,
                port: Optional[int] = None,
                timeout: int = 30) -> CommandResult:
        """
        Execute a command on a remote host via SSH (non-interactive).
        
        Uses SSH with options to disable interactive prompts:
        - BatchMode=yes: Fail rather than prompt for passwords
        - StrictHostKeyChecking=no: Auto-accept new host keys
        - ConnectTimeout: Limit connection time
        
        Args:
            user_host: User and host (e.g., "user@100.71.89.62" or "user@hostname")
            remote_command: Command to execute on remote host
            identity_file: Path to SSH private key (optional)
            port: SSH port (default: 22)
            timeout: Maximum execution time in seconds
            
        Returns:
            CommandResult with stdout, stderr, exit_code
            
        Example:
            runner.run_ssh("roggoz@100.71.89.62", "ps aux | grep -i kokoro")
        """
        # Build SSH options for non-interactive execution
        ssh_opts = [
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-o", "ServerAliveInterval=5",
            "-o", "ServerAliveCountMax=3"
        ]
        
        if identity_file:
            ssh_opts.extend(["-i", identity_file])
        if port:
            ssh_opts.extend(["-p", str(port)])
        
        # Build the full SSH command
        args = ["ssh"] + ssh_opts + [user_host, remote_command]
        
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.cwd,
                encoding='utf-8',
                errors='replace'
            )
            
            cmd_result = CommandResult(
                stdout=result.stdout.strip() if result.stdout else "",
                stderr=result.stderr.strip() if result.stderr else "",
                exit_code=result.returncode,
                command=f"ssh {' '.join(ssh_opts)} {user_host} '{remote_command}'",
                shell_used=self.shell_config.name
            )
            
        except subprocess.TimeoutExpired:
            cmd_result = CommandResult(
                stdout="",
                stderr=f"SSH command timed out after {timeout} seconds",
                exit_code=124,
                command=f"ssh {user_host} '{remote_command}'",
                shell_used=self.shell_config.name
            )
        except FileNotFoundError:
            cmd_result = CommandResult(
                stdout="",
                stderr="SSH client not found. Install OpenSSH client.",
                exit_code=127,
                command=f"ssh {user_host} '{remote_command}'",
                shell_used=self.shell_config.name
            )
        except Exception as e:
            cmd_result = CommandResult(
                stdout="",
                stderr=f"SSH error: {str(e)}",
                exit_code=1,
                command=f"ssh {user_host} '{remote_command}'",
                shell_used=self.shell_config.name
            )
        
        self.command_history.append(cmd_result)
        return cmd_result
    
    def run_tailscale_ssh(self, user_host: str, remote_command: str,
                          timeout: int = 30) -> CommandResult:
        """
        Execute a command on a Tailscale-connected host via 'tailscale ssh'.
        
        Note: 'tailscale ssh' requires authentication to be pre-configured
        (either via Tailscale ACLs or SSH keys). It cannot prompt for 
        passwords in non-interactive mode.
        
        Args:
            user_host: User and host (e.g., "roggoz@100.71.89.62")
            remote_command: Command to execute on remote host
            timeout: Maximum execution time in seconds
            
        Returns:
            CommandResult
            
        Example:
            runner.run_tailscale_ssh("roggoz@100.71.89.62", "systemctl status kokoro-tts")
        """
        args = ["tailscale", "ssh", user_host, remote_command]
        
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.cwd,
                encoding='utf-8',
                errors='replace'
            )
            
            cmd_result = CommandResult(
                stdout=result.stdout.strip() if result.stdout else "",
                stderr=result.stderr.strip() if result.stderr else "",
                exit_code=result.returncode,
                command=f"tailscale ssh {user_host} '{remote_command}'",
                shell_used=self.shell_config.name
            )
            
        except subprocess.TimeoutExpired:
            cmd_result = CommandResult(
                stdout="",
                stderr=(f"tailscale ssh timed out after {timeout}s. "
                        f"Host may be unreachable or authentication required."),
                exit_code=124,
                command=f"tailscale ssh {user_host} '{remote_command}'",
                shell_used=self.shell_config.name
            )
        except FileNotFoundError:
            cmd_result = CommandResult(
                stdout="",
                stderr="tailscale command not found. Is Tailscale installed?",
                exit_code=127,
                command=f"tailscale ssh {user_host} '{remote_command}'",
                shell_used=self.shell_config.name
            )
        except Exception as e:
            cmd_result = CommandResult(
                stdout="",
                stderr=f"tailscale ssh error: {str(e)}",
                exit_code=1,
                command=f"tailscale ssh {user_host} '{remote_command}'",
                shell_used=self.shell_config.name
            )
        
        self.command_history.append(cmd_result)
        return cmd_result
    
    def run_chained(self, commands: list[str], timeout: int = 30) -> CommandResult:
        """
        Run multiple commands chained together.
        
        Args:
            commands: List of commands to chain
            timeout: Maximum execution time in seconds
            
        Returns:
            CommandResult
        """
        # Join commands with the appropriate chain separator
        chained = self.shell_config.chain_separator.join(commands)
        return self.run(chained, timeout)
    
    def create_file(self, path: str, content: str = "") -> CommandResult:
        """Create a file with optional content."""
        cmd = self.shell_config.create_file_cmd.format(
            path=path,
            content=content.replace('"', '\\"')
        )
        return self.run(cmd)
    
    def copy_file(self, src: str, dst: str) -> CommandResult:
        """Copy a file from source to destination."""
        cmd = self.shell_config.copy_file_cmd.format(src=src, dst=dst)
        return self.run(cmd)
    
    def move_file(self, src: str, dst: str) -> CommandResult:
        """Move/rename a file."""
        cmd = self.shell_config.move_file_cmd.format(src=src, dst=dst)
        return self.run(cmd)
    
    def delete_file(self, path: str) -> CommandResult:
        """Delete a file."""
        cmd = self.shell_config.delete_file_cmd.format(path=path)
        return self.run(cmd)
    
    def read_file(self, path: str) -> CommandResult:
        """Read file contents."""
        cmd = self.shell_config.read_file_cmd.format(path=path)
        return self.run(cmd)
    
    def list_directory(self, path: str = ".") -> CommandResult:
        """List directory contents."""
        cmd = self.shell_config.list_dir_cmd.format(path=path)
        return self.run(cmd)
    
    def change_directory(self, path: str) -> bool:
        """Change the working directory."""
        try:
            target = Path(path).resolve()
            if target.exists() and target.is_dir():
                self.cwd = str(target)
                return True
            return False
        except Exception:
            return False
    
    def get_history(self) -> list[CommandResult]:
        """Get command execution history."""
        return self.command_history.copy()
    
    def clear_history(self):
        """Clear command history."""
        self.command_history.clear()


def create_runner_for_os(os_type: OperatingSystem = None, cwd: str = None) -> ShellRunner:
    """
    Factory function to create a ShellRunner for a specific OS.
    
    Args:
        os_type: Target OS. If None, uses current OS.
        cwd: Working directory
        
    Returns:
        Configured ShellRunner instance
    """
    shell_config = OSDetector.get_shell_config(os_type)
    return ShellRunner(shell_config=shell_config, cwd=cwd)


if __name__ == "__main__":
    # Test the shell runner
    print("Testing Shell Runner...")
    print("=" * 50)
    
    runner = ShellRunner()
    print(f"Using shell: {runner.shell_config.name}")
    print(f"Working directory: {runner.cwd}")
    print("-" * 50)
    
    # Test a simple command
    if runner.shell_config.name == "PowerShell":
        result = runner.run('Write-Output "Hello from PowerShell!"')
    else:
        result = runner.run('echo "Hello from Bash!"')
    
    print(f"Command: {result.command}")
    print(f"Exit code: {result.exit_code}")
    print(f"Output: {result.stdout}")
    if result.stderr:
        print(f"Errors: {result.stderr}")
