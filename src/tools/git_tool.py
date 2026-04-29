"""
Git Tool - Version control operations for Rogius.

Supports:
- Repository status and info
- Stage/unstage files
- Commit changes
- Branch operations
- Remote operations
- Log and diff viewing
- Safe operations with validation
"""

import os
import subprocess
import re
from typing import Optional, List, Dict, Any
from .tool_interface import Tool, Action, ActionType, ToolResult
from .tool_registry import tool


@tool(ActionType.GIT_COMMAND)
class GitTool(Tool):
    """
    Tool for Git version control operations.
    
    Provides safe, validated git commands with output parsing.
    Designed for AI workflows that need to interact with git repositories.
    """
    
    # Git operations that are read-only (safe)
    READONLY_OPS = {'status', 'log', 'diff', 'show', 'branch', 'remote', 'config', 'tag'}
    
    # Git operations that modify state (need confirmation)
    MODIFYNG_OPS = {'add', 'commit', 'push', 'pull', 'fetch', 'checkout', 'merge', 'rebase', 'reset', 'clean', 'rm', 'mv'}
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.GIT_COMMAND
    
    async def execute(self, action: Action, env_context: dict) -> ToolResult:
        """
        Execute a git command.
        
        Args:
            action: Action with payload containing git operation
            env_context: Dict with 'working_directory' for repo location
            
        Returns:
            ToolResult with parsed git output
        """
        payload = action.payload
        operation = payload.get("operation", "")
        working_dir = payload.get("cwd") or env_context.get("working_directory", os.getcwd())
        options = payload.get("options", [])
        message = payload.get("message", "")
        files = payload.get("files", [])
        dry_run = payload.get("dry_run", False)
        
        if not operation:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error="No git operation specified"
            )
        
        # Validate operation
        if operation not in self.READONLY_OPS and operation not in self.MODIFYNG_OPS:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error=f"Unknown git operation: {operation}"
            )
        
        # Safety check for modifying operations
        if operation in self.MODIFYNG_OPS and not payload.get("confirmed", False) and not dry_run:
            return ToolResult(
                success=False,
                output="",
                artifacts={
                    "operation": operation,
                    "requires_confirmation": True,
                    "dry_run": True
                },
                error=f"Operation '{operation}' modifies repository state. Set 'confirmed': true to execute."
            )
        
        try:
            # Build command
            cmd_parts = ['git', operation]
            
            # Add common options
            if dry_run and operation in ['clean', 'reset']:
                cmd_parts.append('--dry-run')
            
            if '-n' in options or '--dry-run' in options:
                dry_run = True
            
            cmd_parts.extend(options)
            
            # Add message for commit
            if operation == 'commit' and message:
                cmd_parts.extend(['-m', message])
            
            # Add files
            if files:
                cmd_parts.extend(files)
            
            # Execute command
            result = self._run_git(cmd_parts, working_dir)
            
            # Parse output based on operation
            parsed_output = self._parse_output(operation, result['stdout'], result['stderr'])
            
            return ToolResult(
                success=result['returncode'] == 0,
                output=result['stdout'] or result['stderr'] or '(no output)',
                artifacts={
                    "operation": operation,
                    "working_directory": working_dir,
                    "exit_code": result['returncode'],
                    "stdout": result['stdout'],
                    "stderr": result['stderr'],
                    "parsed": parsed_output,
                    "dry_run": dry_run
                },
                error=result['stderr'] if result['returncode'] != 0 else None
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error=f"Git operation failed: {str(e)}"
            )
    
    def _run_git(self, cmd_parts: List[str], cwd: str) -> dict:
        """Execute git command and return output."""
        env = os.environ.copy()
        # Prevent git from opening interactive editors
        env['GIT_EDITOR'] = 'true'
        env['EDITOR'] = 'true'
        
        try:
            result = subprocess.run(
                cmd_parts,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
                timeout=60
            )
            
            return {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                'returncode': 124,
                'stdout': '',
                'stderr': 'Git operation timed out after 60 seconds'
            }
        except FileNotFoundError:
            return {
                'returncode': 127,
                'stdout': '',
                'stderr': 'Git command not found. Is git installed?'
            }
    
    def _parse_output(self, operation: str, stdout: str, stderr: str) -> dict:
        """Parse git command output into structured data."""
        
        if operation == 'status':
            return self._parse_status(stdout + stderr)
        elif operation == 'log':
            return self._parse_log(stdout)
        elif operation == 'diff':
            return self._parse_diff(stdout)
        elif operation == 'branch':
            return self._parse_branch(stdout)
        elif operation == 'remote':
            return self._parse_remote(stdout)
        
        return {"raw": stdout + stderr}
    
    def _parse_status(self, output: str) -> dict:
        """Parse git status output."""
        staged = []
        unstaged = []
        untracked = []
        branch = None
        ahead_behind = None
        
        for line in output.split('\n'):
            line = line.strip()
            
            # Parse branch info
            if line.startswith('On branch'):
                branch = line.replace('On branch ', '').strip()
            elif 'Changes to be committed' in line:
                continue
            elif 'Changes not staged' in line:
                continue
            elif 'Untracked files' in line:
                continue
            elif line.startswith('Your branch is'):
                ahead_behind = line.replace('Your branch is ', '').strip()
            
            # Parse file states
            elif line.startswith('M') or line.startswith('A') or line.startswith('D') or line.startswith('R'):
                # Staged changes
                file = line[2:].strip()
                if file:
                    staged.append({"file": file, "status": line[0]})
            elif line.startswith(' M') or line.startswith(' D') or line.startswith('??'):
                # Unstaged or untracked
                file = line[3:].strip()
                if file:
                    if line.startswith('??'):
                        untracked.append(file)
                    else:
                        unstaged.append({"file": file, "status": line[2]})
        
        is_clean = not staged and not unstaged and not untracked
        
        return {
            "branch": branch,
            "ahead_behind": ahead_behind,
            "is_clean": is_clean,
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked,
            "staged_count": len(staged),
            "unstaged_count": len(unstaged),
            "untracked_count": len(untracked)
        }
    
    def _parse_log(self, output: str) -> list:
        """Parse git log output (assuming --oneline format)."""
        commits = []
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Parse: hash (optional refs) message
            match = re.match(r'^([a-f0-9]+)\s+(?:\(([^)]+)\)\s+)?(.+)$', line)
            if match:
                commits.append({
                    "hash": match.group(1),
                    "refs": match.group(2),
                    "message": match.group(3)
                })
            else:
                commits.append({"raw": line})
        
        return commits
    
    def _parse_diff(self, output: str) -> dict:
        """Parse git diff output."""
        files = []
        current_file = None
        
        for line in output.split('\n'):
            if line.startswith('diff --git'):
                if current_file:
                    files.append(current_file)
                parts = line.split()
                if len(parts) >= 4:
                    current_file = {
                        "path": parts[-1].replace('b/', ''),
                        "old_path": parts[-2].replace('a/', ''),
                        "chunks": []
                    }
            elif line.startswith('@@'):
                if current_file:
                    current_file["chunks"].append({"header": line})
            elif line.startswith('+') and not line.startswith('+++'):
                if current_file and current_file["chunks"]:
                    current_file["chunks"][-1].setdefault("added", []).append(line[1:])
            elif line.startswith('-') and not line.startswith('---'):
                if current_file and current_file["chunks"]:
                    current_file["chunks"][-1].setdefault("removed", []).append(line[1:])
        
        if current_file:
            files.append(current_file)
        
        return {"files": files, "file_count": len(files)}
    
    def _parse_branch(self, output: str) -> dict:
        """Parse git branch output."""
        branches = []
        current = None
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('*'):
                current = line[1:].strip()
                branches.append({"name": current, "current": True})
            else:
                branches.append({"name": line, "current": False})
        
        return {
            "branches": branches,
            "current": current,
            "count": len(branches)
        }
    
    def _parse_remote(self, output: str) -> dict:
        """Parse git remote output."""
        remotes = []
        
        for line in output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if len(parts) >= 2:
                remotes.append({
                    "name": parts[0],
                    "url": parts[1],
                    "type": parts[2] if len(parts) > 2 else None
                })
        
        return {"remotes": remotes, "count": len(remotes)}
    
    def verify(self, action: Action, result: ToolResult) -> dict:
        """Verify git operation results."""
        artifacts = result.artifacts
        operation = artifacts.get("operation", "")
        exit_code = artifacts.get("exit_code", 1)
        
        verification = {
            "tool_verified": result.success,
            "exit_code": exit_code,
            "operation": operation
        }
        
        # Operation-specific verification
        if operation == 'status':
            parsed = artifacts.get("parsed", {})
            verification["is_clean"] = parsed.get("is_clean", False)
            verification["has_changes"] = (
                parsed.get("staged_count", 0) > 0 or
                parsed.get("unstaged_count", 0) > 0
            )
        elif operation == 'commit':
            verification["committed"] = exit_code == 0 and "nothing to commit" not in (result.error or "")
        
        return verification
    
    def classify_failure(self, result: ToolResult) -> str:
        """Classify git failures."""
        error = result.error or ""
        stderr = result.artifacts.get("stderr", "")
        combined = (error + stderr).lower()
        
        if "not a git repository" in combined:
            return "not_a_repo"
        elif "permission denied" in combined or "access denied" in combined:
            return "permission_denied"
        elif "could not resolve" in combined or "unable to access" in combined:
            return "network_error"
        elif "merge conflict" in combined or "conflict" in combined:
            return "merge_conflict"
        elif "nothing to commit" in combined:
            return "nothing_to_commit"
        elif "your branch is ahead" in combined:
            return "unpushed_commits"
        elif "git command not found" in combined:
            return "git_not_installed"
        
        return "unknown"
    
    def apply_failure_fix(self, action: Action, hint: str) -> Optional[Action]:
        """Apply fixes for common git failures."""
        payload = action.payload.copy()
        operation = payload.get("operation", "")
        
        if hint == "nothing_to_commit":
            # Try to stage files first
            if operation == 'commit':
                # Can't auto-fix this - need user decision
                return None
        
        elif hint == "not_a_repo":
            # Suggest git init
            payload["operation"] = "init"
            payload["confirmed"] = False  # Still needs confirmation
            return Action(
                type=action.type,
                payload=payload,
                description=f"{action.description} (fix: suggest git init)",
                timeout=action.timeout
            )
        
        elif hint == "unpushed_commits" and operation == 'push':
            # This is actually a success case - commits exist to push
            return None
        
        return None
    
    def get_schema(self) -> dict:
        """Return schema for git_command action."""
        return {
            "type": "git_command",
            "description": "Execute git version control operations with safety checks",
            "payload_schema": {
                "operation": "string - Git command (status, add, commit, push, pull, log, diff, branch, checkout, etc.)",
                "cwd": "string - Working directory (optional, defaults to env context)",
                "options": "list - Additional git options/flags",
                "message": "string - Commit message (for commit operation)",
                "files": "list - Files to operate on (for add, checkout, etc.)",
                "confirmed": "boolean - Set to true to execute modifying operations",
                "dry_run": "boolean - Preview changes without applying (for supported operations)"
            },
            "readonly_operations": list(self.READONLY_OPS),
            "modifying_operations": list(self.MODIFYNG_OPS),
            "failure_hints": ["not_a_repo", "permission_denied", "network_error", "merge_conflict", "nothing_to_commit", "unpushed_commits", "git_not_installed"]
        }
    
    def get_examples(self) -> list[dict]:
        """Return example git_command actions."""
        return [
            {
                "operation": "status",
                "cwd": "."
            },
            {
                "operation": "add",
                "files": ["src/main.py", "README.md"],
                "confirmed": True
            },
            {
                "operation": "commit",
                "message": "Update main.py and README",
                "confirmed": True
            },
            {
                "operation": "log",
                "options": ["--oneline", "-n", "5"]
            }
        ]
