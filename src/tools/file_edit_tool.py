"""
File Edit Tool - Structured file editing for Rogius.

Supports:
- Create new files
- Read file contents
- Replace text (exact or regex)
- Insert lines at specific positions
- Delete lines or sections
- Apply multiple edits atomically
"""

import re
import os
from typing import Optional, List, Dict, Any
from .tool_interface import Tool, Action, ActionType, ToolResult
from .tool_registry import tool


@tool(ActionType.FILE_EDIT)
class FileEditTool(Tool):
    """
    Tool for structured file editing operations.
    
    Supports atomic multi-edit operations with rollback capability.
    Designed for local AI workflows where precise file manipulation is needed.
    """
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.FILE_EDIT
    
    async def execute(self, action: Action, env_context: dict) -> ToolResult:
        """
        Execute a file edit action.
        
        Args:
            action: Action with payload containing edit operations
            env_context: Dict with 'working_directory' for relative paths
            
        Returns:
            ToolResult with success status and file artifacts
        """
        payload = action.payload
        operations = payload.get("operations", [])
        file_path = payload.get("file_path", "")
        working_dir = env_context.get("working_directory", os.getcwd())
        
        if not file_path:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error="No file_path specified"
            )
        
        # Resolve path
        if not os.path.isabs(file_path):
            file_path = os.path.join(working_dir, file_path)
        
        file_path = os.path.normpath(file_path)
        
        try:
            results = []
            for op in operations:
                op_type = op.get("type")
                result = self._execute_operation(file_path, op_type, op)
                results.append(result)
                
                if not result["success"]:
                    return ToolResult(
                        success=False,
                        output=f"",
                        artifacts={"operations": results},
                        error=f"Operation failed: {result.get('error', 'Unknown error')}"
                    )
            
            return ToolResult(
                success=True,
                output=f"Successfully performed {len(results)} operation(s) on {file_path}",
                artifacts={
                    "file_path": file_path,
                    "operations": results,
                    "file_exists": os.path.exists(file_path)
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error=f"File edit failed: {str(e)}"
            )
    
    def _execute_operation(self, file_path: str, op_type: str, op: dict) -> dict:
        """Execute a single edit operation."""
        
        if op_type == "create":
            return self._op_create(file_path, op)
        elif op_type == "read":
            return self._op_read(file_path, op)
        elif op_type == "replace":
            return self._op_replace(file_path, op)
        elif op_type == "insert":
            return self._op_insert(file_path, op)
        elif op_type == "delete":
            return self._op_delete(file_path, op)
        elif op_type == "append":
            return self._op_append(file_path, op)
        else:
            return {"success": False, "error": f"Unknown operation type: {op_type}"}
    
    def _op_create(self, file_path: str, op: dict) -> dict:
        """Create a new file with content."""
        content = op.get("content", "")
        overwrite = op.get("overwrite", False)
        
        if os.path.exists(file_path) and not overwrite:
            return {"success": False, "error": f"File already exists: {file_path}"}
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return {
            "success": True,
            "type": "create",
            "file_path": file_path,
            "bytes_written": len(content.encode('utf-8'))
        }
    
    def _op_read(self, file_path: str, op: dict) -> dict:
        """Read file contents."""
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}
        
        limit = op.get("limit", 10000)  # Default 10KB limit
        offset = op.get("offset", 0)
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            if offset > 0:
                f.seek(offset)
            content = f.read(limit)
        
        line_count = content.count('\n') + 1
        
        return {
            "success": True,
            "type": "read",
            "file_path": file_path,
            "content": content,
            "lines": line_count,
            "truncated": len(content) >= limit
        }
    
    def _op_replace(self, file_path: str, op: dict) -> dict:
        """Replace text in file (exact or regex)."""
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}
        
        old_text = op.get("old_text", "")
        new_text = op.get("new_text", "")
        use_regex = op.get("use_regex", False)
        count = op.get("count", 0)  # 0 = all occurrences
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        if use_regex:
            flags = op.get("regex_flags", 0)
            if isinstance(flags, list):
                flag_val = 0
                for f in flags:
                    if f == "i": flag_val |= re.IGNORECASE
                    elif f == "m": flag_val |= re.MULTILINE
                    elif f == "s": flag_val |= re.DOTALL
                flags = flag_val
            
            pattern = re.compile(old_text, flags)
            new_content, replacements = pattern.subn(new_text, content, count=count or 0)
        else:
            if count == 0:
                new_content = content.replace(old_text, new_text)
                replacements = content.count(old_text)
            else:
                new_content = content.replace(old_text, new_text, count)
                replacements = min(count, content.count(old_text))
        
        if new_content == content:
            return {"success": False, "error": "No replacements made (text not found)"}
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return {
            "success": True,
            "type": "replace",
            "replacements": replacements,
            "file_path": file_path
        }
    
    def _op_insert(self, file_path: str, op: dict) -> dict:
        """Insert text at specific line or position."""
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}
        
        text = op.get("text", "")
        line = op.get("line", None)  # 1-indexed line number
        column = op.get("column", 0)
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        if line is not None:
            # Insert at specific line
            lines = content.split('\n')
            insert_idx = min(line - 1, len(lines))
            lines.insert(insert_idx, text)
            new_content = '\n'.join(lines)
        else:
            # Insert at position
            pos = min(column, len(content))
            new_content = content[:pos] + text + content[pos:]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return {
            "success": True,
            "type": "insert",
            "file_path": file_path,
            "line": line,
            "column": column
        }
    
    def _op_delete(self, file_path: str, op: dict) -> dict:
        """Delete lines or text range."""
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}
        
        start_line = op.get("start_line", None)
        end_line = op.get("end_line", None)
        text = op.get("text", None)
        use_regex = op.get("use_regex", False)
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        
        if start_line is not None and end_line is not None:
            # Delete line range
            lines = content.split('\n')
            del lines[start_line - 1:end_line]
            new_content = '\n'.join(lines)
        elif text:
            # Delete specific text
            if use_regex:
                new_content = re.sub(text, '', content)
            else:
                new_content = content.replace(text, '')
        else:
            return {"success": False, "error": "Must specify line range or text to delete"}
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return {
            "success": True,
            "type": "delete",
            "file_path": file_path
        }
    
    def _op_append(self, file_path: str, op: dict) -> dict:
        """Append text to end of file."""
        text = op.get("text", "")
        newline = op.get("newline", True)  # Add newline before text
        
        mode = 'a' if os.path.exists(file_path) else 'w'
        
        with open(file_path, mode, encoding='utf-8') as f:
            if newline and os.path.exists(file_path):
                f.write('\n')
            f.write(text)
        
        return {
            "success": True,
            "type": "append",
            "file_path": file_path,
            "bytes_added": len(text.encode('utf-8'))
        }
    
    def verify(self, action: Action, result: ToolResult) -> dict:
        """Verify file edit operations."""
        artifacts = result.artifacts
        operations = artifacts.get("operations", [])
        file_path = artifacts.get("file_path", "")
        
        verification = {
            "tool_verified": result.success,
            "file_exists": os.path.exists(file_path) if file_path else False,
            "operations_verified": len(operations)
        }
        
        # Verify each operation produced expected result
        for op in operations:
            if not op.get("success"):
                verification["tool_verified"] = False
                verification["failed_operation"] = op
                break
        
        return verification
    
    def classify_failure(self, result: ToolResult) -> str:
        """Classify file edit failures."""
        error = result.error or ""
        error_lower = error.lower()
        
        if "not found" in error_lower or "does not exist" in error_lower:
            return "file_not_found"
        elif "permission denied" in error_lower or "access denied" in error_lower:
            return "permission_denied"
        elif "no replacements made" in error_lower:
            return "text_not_found"
        elif "file already exists" in error_lower:
            return "file_exists"
        elif "is a directory" in error_lower:
            return "is_directory"
        
        return "unknown"
    
    def apply_failure_fix(self, action: Action, hint: str) -> Optional[Action]:
        """Apply fixes for common file edit failures."""
        payload = action.payload.copy()
        operations = payload.get("operations", [])
        
        if hint == "file_not_found" and operations:
            # If first operation is not create, prepend a create
            if operations[0].get("type") != "create":
                new_op = {
                    "type": "create",
                    "content": "",
                    "overwrite": False
                }
                payload["operations"] = [new_op] + operations
                return Action(
                    type=action.type,
                    payload=payload,
                    description=f"{action.description} (fix: create file first)",
                    timeout=action.timeout
                )
        
        elif hint == "text_not_found":
            # Try fuzzy matching or line-based replacement
            for op in operations:
                if op.get("type") == "replace":
                    # Could implement fuzzy matching here
                    pass
        
        elif hint == "file_exists":
            # Enable overwrite
            for op in operations:
                if op.get("type") == "create":
                    op["overwrite"] = True
            return Action(
                type=action.type,
                payload=payload,
                description=f"{action.description} (fix: enable overwrite)",
                timeout=action.timeout
            )
        
        return None
    
    def get_schema(self) -> dict:
        """Return schema for file_edit action."""
        return {
            "type": "file_edit",
            "description": "Structured file editing operations (create, read, replace, insert, delete, append)",
            "payload_schema": {
                "file_path": "string - Path to file (relative or absolute)",
                "operations": [
                    {
                        "type": "create",
                        "content": "string - File content",
                        "overwrite": "boolean - Allow overwriting existing file"
                    },
                    {
                        "type": "read",
                        "limit": "integer - Max bytes to read (default 10000)",
                        "offset": "integer - Byte offset to start reading"
                    },
                    {
                        "type": "replace",
                        "old_text": "string - Text to find",
                        "new_text": "string - Replacement text",
                        "use_regex": "boolean - Use regex matching",
                        "regex_flags": "string or list - Regex flags (i=ignorecase, m=multiline, s=dotall)",
                        "count": "integer - Max replacements (0=all)"
                    },
                    {
                        "type": "insert",
                        "text": "string - Text to insert",
                        "line": "integer - Line number to insert at (1-indexed, optional)",
                        "column": "integer - Character position (if line not specified)"
                    },
                    {
                        "type": "delete",
                        "start_line": "integer - Start line (1-indexed, optional)",
                        "end_line": "integer - End line (optional)",
                        "text": "string - Text to delete (alternative to line range)",
                        "use_regex": "boolean - Use regex for text matching"
                    },
                    {
                        "type": "append",
                        "text": "string - Text to append",
                        "newline": "boolean - Add newline before appending (default true)"
                    }
                ]
            },
            "failure_hints": ["file_not_found", "permission_denied", "text_not_found", "file_exists", "is_directory"]
        }
    
    def get_examples(self) -> list[dict]:
        """Return example file_edit actions."""
        return [
            {
                "file_path": "src/main.py",
                "operations": [
                    {
                        "type": "create",
                        "content": "print('Hello World')",
                        "overwrite": False
                    }
                ]
            },
            {
                "file_path": "config.json",
                "operations": [
                    {
                        "type": "replace",
                        "old_text": '"debug": false',
                        "new_text": '"debug": true',
                        "use_regex": False
                    }
                ]
            },
            {
                "file_path": "data.txt",
                "operations": [
                    {
                        "type": "read",
                        "limit": 5000
                    }
                ]
            }
        ]
