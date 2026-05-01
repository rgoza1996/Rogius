"""
OS Detection and Shell Selection Launcher

Detects if the PC is Linux/macOS or Windows, then selects
the appropriate shell (bash for Linux, PowerShell for Windows).
"""

import platform
import sys
import os
import subprocess
from enum import Enum
from dataclasses import dataclass


class OperatingSystem(Enum):
    """Supported operating systems."""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    UNKNOWN = "unknown"


@dataclass
class ShellConfig:
    """Configuration for a shell."""
    name: str
    executable: str
    shell_args: list[str]
    create_file_cmd: str
    copy_file_cmd: str
    move_file_cmd: str
    delete_file_cmd: str
    read_file_cmd: str
    list_dir_cmd: str
    chain_separator: str
    path_separator: str


class OSDetector:
    """Detects the operating system and provides shell configuration."""
    
    @staticmethod
    def detect() -> OperatingSystem:
        """Detect the current operating system."""
        system = platform.system().lower()
        
        if system == "windows":
            return OperatingSystem.WINDOWS
        elif system == "linux":
            return OperatingSystem.LINUX
        elif system == "darwin":
            return OperatingSystem.MACOS
        else:
            return OperatingSystem.UNKNOWN
    
    @staticmethod
    def get_shell_config(os_type: OperatingSystem = None) -> ShellConfig:
        """Get shell configuration for the detected OS."""
        if os_type is None:
            os_type = OSDetector.detect()
        
        if os_type == OperatingSystem.WINDOWS:
            return ShellConfig(
                name="PowerShell",
                executable="powershell.exe",
                shell_args=["-Command"],
                create_file_cmd='Set-Content -Path "{path}" -Value "{content}"',
                copy_file_cmd='Copy-Item -Path "{src}" -Destination "{dst}"',
                move_file_cmd='Move-Item -Path "{src}" -Destination "{dst}"',
                delete_file_cmd='Remove-Item -Path "{path}"',
                read_file_cmd='Get-Content -Path "{path}"',
                list_dir_cmd='Get-ChildItem -Path "{path}"',
                chain_separator="; ",
                path_separator="\\"
            )
        else:
            # Linux/macOS - use bash
            return ShellConfig(
                name="Bash",
                executable="bash",
                shell_args=["-c"],
                create_file_cmd='echo "{content}" > "{path}"',
                copy_file_cmd='cp "{src}" "{dst}"',
                move_file_cmd='mv "{src}" "{dst}"',
                delete_file_cmd='rm "{path}"',
                read_file_cmd='cat "{path}"',
                list_dir_cmd='ls -la "{path}"',
                chain_separator=" && ",
                path_separator="/"
            )
    
    @staticmethod
    def get_system_info() -> dict:
        """Get system information."""
        os_type = OSDetector.detect()
        shell_config = OSDetector.get_shell_config(os_type)
        
        # Helper to run command and get output
        def run_cmd(cmd: list[str]) -> str:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                return result.stdout.strip() if result.returncode == 0 else "not installed"
            except:
                return "not installed"
        
        # Detect package manager
        if os_type == OperatingSystem.WINDOWS:
            pkg_manager = "winget (Windows Package Manager)"
            # Check for admin rights on Windows
            is_admin = run_cmd(["powershell", "-Command", "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)"]) == "True"
        else:
            # Linux package managers
            if run_cmd(["which", "apt"]) != "not installed":
                pkg_manager = "apt (Debian/Ubuntu)"
            elif run_cmd(["which", "yum"]) != "not installed":
                pkg_manager = "yum (RHEL/CentOS)"
            elif run_cmd(["which", "pacman"]) != "not installed":
                pkg_manager = "pacman (Arch)"
            elif run_cmd(["which", "apk"]) != "not installed":
                pkg_manager = "apk (Alpine)"
            else:
                pkg_manager = "unknown"
            # Check sudo on Linux
            is_admin = run_cmd(["sudo", "-n", "true"]) == ""
        
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "shell": shell_config.name,
            "shell_executable": shell_config.executable,
            "hostname": platform.node(),
            "username": os.getenv("USER") or os.getenv("USERNAME") or "unknown",
            "package_manager": pkg_manager,
            "has_sudo": is_admin,
            "node_version": run_cmd(["node", "--version"]),
            "docker_version": run_cmd(["docker", "--version"])
        }


def print_detection_results():
    """Print OS detection results for debugging."""
    os_type = OSDetector.detect()
    shell_config = OSDetector.get_shell_config(os_type)
    system_info = OSDetector.get_system_info()
    
    print("=" * 50)
    print("OS DETECTION RESULTS")
    print("=" * 50)
    print(f"Operating System: {os_type.value}")
    print(f"Platform: {system_info['os']} {system_info['os_version']}")
    print(f"Architecture: {system_info['architecture']}")
    print(f"Processor: {system_info['processor']}")
    print(f"Python Version: {system_info['python_version']}")
    print(f"Hostname: {system_info['hostname']}")
    print(f"Username: {system_info['username']}")
    print("-" * 50)
    print(f"Selected Shell: {shell_config.name}")
    print(f"Shell Executable: {shell_config.executable}")
    print(f"Shell Arguments: {shell_config.shell_args}")
    print("=" * 50)


def start_api_server(port: int = 8000, host: str = "127.0.0.1") -> None:
    """
    Start the FastAPI server for webapp backend integration.
    
    Args:
        port: Port number for the server (default: 8000)
        host: Host to bind to (default: 127.0.0.1)
    """
    import subprocess
    import sys
    from pathlib import Path
    
    api_server_path = Path(__file__).parent / "api_server.py"
    
    if not api_server_path.exists():
        print(f"Error: API server not found at {api_server_path}")
        return
    
    print(f"Starting Rogius Python API Server on {host}:{port}...")
    print(f"API docs available at: http://{host}:{port}/docs")
    
    try:
        # Start uvicorn in a subprocess
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api_server:app", "--host", host, "--port", str(port)],
            cwd=str(api_server_path.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Write PID to file for management
        pid_file = Path(__file__).parent / ".api_server.pid"
        pid_file.write_text(str(process.pid))
        
        print(f"API server started with PID: {process.pid}")
        print(f"PID file: {pid_file}")
        
        return process
        
    except Exception as e:
        print(f"Failed to start API server: {e}")
        return None


def stop_api_server() -> bool:
    """Stop the running API server."""
    import signal
    import os
    from pathlib import Path
    
    pid_file = Path(__file__).parent / ".api_server.pid"
    
    if not pid_file.exists():
        print("No API server PID file found")
        return False
    
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink()
        print(f"API server (PID {pid}) stopped")
        return True
    except Exception as e:
        print(f"Failed to stop API server: {e}")
        return False


def is_api_server_running(port: int = 8000) -> bool:
    """Check if the API server is running."""
    import urllib.request
    
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
        return True
    except:
        return False


if __name__ == "__main__":
    print_detection_results()
