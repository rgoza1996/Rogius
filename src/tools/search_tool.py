"""
Search Tool - Fast code search using ripgrep for Rogius.

Supports:
- Text and regex search
- File type filtering
- Search within specific directories
- Case sensitivity control
- Context lines
- Results with file paths, line numbers, and snippets
"""

import os
import subprocess
import re
from typing import Optional, List, Dict, Any
from .tool_interface import Tool, Action, ActionType, ToolResult
from .tool_registry import tool


@tool(ActionType.CODE_SEARCH)
class SearchTool(Tool):
    """
    Tool for fast code search using ripgrep.
    
    Falls back to grep or Python search if ripgrep is not available.
    Optimized for local AI workflows that need quick codebase exploration.
    """
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.CODE_SEARCH
    
    async def execute(self, action: Action, env_context: dict) -> ToolResult:
        """
        Execute a code search.
        
        Args:
            action: Action with payload containing search parameters
            env_context: Dict with 'working_directory' for search root
            
        Returns:
            ToolResult with search results
        """
        payload = action.payload
        query = payload.get("query", "")
        search_dir = payload.get("search_dir", "") or env_context.get("working_directory", os.getcwd())
        
        # Search options
        use_regex = payload.get("use_regex", False)
        case_sensitive = payload.get("case_sensitive", False)
        file_pattern = payload.get("file_pattern", "")
        file_type = payload.get("file_type", "")  # e.g., 'py', 'js', 'ts'
        max_results = payload.get("max_results", 50)
        context_lines = payload.get("context_lines", 2)  # Lines of context around match
        include_hidden = payload.get("include_hidden", False)
        
        if not query:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error="No search query specified"
            )
        
        try:
            # Determine which search tool to use
            searcher = self._get_searcher()
            
            if searcher == 'ripgrep':
                results = self._search_ripgrep(
                    query, search_dir, use_regex, case_sensitive,
                    file_pattern, file_type, max_results, context_lines, include_hidden
                )
            elif searcher == 'grep':
                results = self._search_grep(
                    query, search_dir, use_regex, case_sensitive,
                    file_pattern, max_results
                )
            else:
                results = self._search_python(
                    query, search_dir, use_regex, case_sensitive,
                    file_pattern, max_results
                )
            
            # Process and format results
            formatted = self._format_results(results, max_results)
            
            return ToolResult(
                success=True,
                output=f"Found {formatted['match_count']} matches in {formatted['file_count']} files",
                artifacts={
                    "query": query,
                    "search_directory": search_dir,
                    "searcher": searcher,
                    "results": formatted['results'],
                    "match_count": formatted['match_count'],
                    "file_count": formatted['file_count'],
                    "truncated": formatted['truncated']
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                artifacts={},
                error=f"Search failed: {str(e)}"
            )
    
    def _get_searcher(self) -> str:
        """Determine which search tool is available."""
        try:
            subprocess.run(['rg', '--version'], capture_output=True, check=True)
            return 'ripgrep'
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        try:
            subprocess.run(['grep', '--version'], capture_output=True, check=True)
            return 'grep'
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return 'python'
    
    def _search_ripgrep(self, query: str, search_dir: str, use_regex: bool,
                        case_sensitive: bool, file_pattern: str, file_type: str,
                        max_results: int, context_lines: int, include_hidden: bool) -> list:
        """Search using ripgrep."""
        cmd = ['rg', '--json']  # JSON output for structured results
        
        if not use_regex:
            cmd.append('--fixed-strings')
        
        if not case_sensitive:
            cmd.append('--ignore-case')
        
        if context_lines > 0:
            cmd.extend(['-C', str(context_lines)])
        
        if file_pattern:
            cmd.extend(['-g', file_pattern])
        
        if file_type:
            cmd.extend(['-t', file_type])
        
        if include_hidden:
            cmd.append('--hidden')
        else:
            cmd.append('--no-hidden')
        
        # Add max count limit
        cmd.extend(['-m', str(max_results * 5)])  # Get more for deduplication
        
        # Add query and directory
        cmd.append(query)
        cmd.append(search_dir)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=30
            )
            
            return self._parse_ripgrep_output(result.stdout)
        except subprocess.TimeoutExpired:
            return []
    
    def _parse_ripgrep_output(self, output: str) -> list:
        """Parse ripgrep JSON output."""
        import json
        results = []
        
        for line in output.strip().split('\n'):
            if not line:
                continue
            
            try:
                data = json.loads(line)
                
                if data.get('type') == 'match':
                    match_data = data.get('data', {})
                    path = match_data.get('path', {}).get('text', '')
                    lines = match_data.get('lines', {}).get('text', '')
                    line_num = match_data.get('line_number', 0)
                    submatches = match_data.get('submatches', [])
                    
                    # Calculate match positions
                    matches = []
                    for sm in submatches:
                        matches.append({
                            "start": sm.get('start', 0),
                            "end": sm.get('end', 0),
                            "text": sm.get('match', {}).get('text', '')
                        })
                    
                    results.append({
                        "file": path,
                        "line": line_num,
                        "text": lines,
                        "matches": matches
                    })
                    
            except json.JSONDecodeError:
                continue
        
        return results
    
    def _search_grep(self, query: str, search_dir: str, use_regex: bool,
                     case_sensitive: bool, file_pattern: str, max_results: int) -> list:
        """Fallback search using grep."""
        cmd = ['grep', '-r', '-n']
        
        if not case_sensitive:
            cmd.append('-i')
        
        if use_regex:
            cmd.append('-E')  # Extended regex
        else:
            cmd.append('-F')  # Fixed strings
        
        cmd.append('-m')
        cmd.append(str(max_results))
        
        cmd.append(query)
        cmd.append(search_dir)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=30
            )
            
            return self._parse_grep_output(result.stdout)
        except subprocess.TimeoutExpired:
            return []
    
    def _parse_grep_output(self, output: str) -> list:
        """Parse grep output format: file:line:text."""
        results = []
        
        for line in output.strip().split('\n'):
            if not line:
                continue
            
            # Parse format: path:line_number:matched_line
            match = re.match(r'^(.+?):(\d+):(.*)$', line)
            if match:
                results.append({
                    "file": match.group(1),
                    "line": int(match.group(2)),
                    "text": match.group(3),
                    "matches": []  # Grep doesn't provide submatch positions
                })
        
        return results
    
    def _search_python(self, query: str, search_dir: str, use_regex: bool,
                       case_sensitive: bool, file_pattern: str, max_results: int) -> list:
        """Pure Python fallback search."""
        results = []
        compiled_pattern = None
        
        if use_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                compiled_pattern = re.compile(query, flags)
            except re.error:
                return []
        else:
            if not case_sensitive:
                query = query.lower()
        
        # Build file filter
        if file_pattern:
            file_regex = re.compile(file_pattern.replace('*', '.*').replace('?', '.'))
        else:
            file_regex = None
        
        count = 0
        for root, dirs, files in os.walk(search_dir):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for filename in files:
                if file_regex and not file_regex.match(filename):
                    continue
                
                filepath = os.path.join(root, filename)
                
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        for line_num, line in enumerate(f, 1):
                            line_stripped = line.rstrip('\n')
                            
                            if use_regex and compiled_pattern:
                                matches = list(compiled_pattern.finditer(line_stripped))
                                if matches:
                                    match_data = [
                                        {"start": m.start(), "end": m.end(), "text": m.group()}
                                        for m in matches
                                    ]
                                    results.append({
                                        "file": filepath,
                                        "line": line_num,
                                        "text": line_stripped,
                                        "matches": match_data
                                    })
                                    count += 1
                            else:
                                search_in = line_stripped if case_sensitive else line_stripped.lower()
                                if query in search_in:
                                    # Find position
                                    pos = search_in.find(query)
                                    results.append({
                                        "file": filepath,
                                        "line": line_num,
                                        "text": line_stripped,
                                        "matches": [{"start": pos, "end": pos + len(query), "text": query}]
                                    })
                                    count += 1
                            
                            if count >= max_results:
                                return results
                                
                except (IOError, OSError, UnicodeDecodeError):
                    continue
        
        return results
    
    def _format_results(self, results: list, max_results: int) -> dict:
        """Format and deduplicate search results."""
        # Deduplicate by file
        seen_files = set()
        formatted = []
        
        for r in results[:max_results]:
            file_path = r.get("file", "")
            seen_files.add(file_path)
            
            formatted.append({
                "file": file_path,
                "line": r.get("line", 0),
                "text": r.get("text", ""),
                "matches": r.get("matches", [])
            })
        
        return {
            "results": formatted,
            "match_count": len(formatted),
            "file_count": len(seen_files),
            "truncated": len(results) > max_results
        }
    
    def verify(self, action: Action, result: ToolResult) -> dict:
        """Verify search results."""
        artifacts = result.artifacts
        match_count = artifacts.get("match_count", 0)
        
        return {
            "tool_verified": result.success,
            "has_results": match_count > 0,
            "match_count": match_count,
            "file_count": artifacts.get("file_count", 0),
            "searcher_used": artifacts.get("searcher", "unknown")
        }
    
    def classify_failure(self, result: ToolResult) -> str:
        """Classify search failures."""
        error = result.error or ""
        error_lower = error.lower()
        
        if "not found" in error_lower or "no such file" in error_lower:
            return "search_dir_not_found"
        elif "permission denied" in error_lower:
            return "permission_denied"
        elif "timeout" in error_lower:
            return "search_timeout"
        elif "invalid regex" in error_lower or "unterminated" in error_lower:
            return "invalid_regex"
        
        return "unknown"
    
    def apply_failure_fix(self, action: Action, hint: str) -> Optional[Action]:
        """Apply fixes for common search failures."""
        payload = action.payload.copy()
        
        if hint == "invalid_regex":
            # Escape regex special characters and switch to fixed strings
            query = payload.get("query", "")
            payload["query"] = re.escape(query)
            payload["use_regex"] = False
            return Action(
                type=action.type,
                payload=payload,
                description=f"{action.description} (fix: escaped regex characters)",
                timeout=action.timeout
            )
        
        elif hint == "search_dir_not_found":
            # Use current directory
            payload["search_dir"] = "."
            return Action(
                type=action.type,
                payload=payload,
                description=f"{action.description} (fix: using current directory)",
                timeout=action.timeout
            )
        
        return None
    
    def get_schema(self) -> dict:
        """Return schema for code_search action."""
        return {
            "type": "code_search",
            "description": "Fast code search using ripgrep (or fallback to grep/Python)",
            "payload_schema": {
                "query": "string - Search query text or pattern",
                "search_dir": "string - Directory to search (optional, defaults to working directory)",
                "use_regex": "boolean - Treat query as regex pattern (default false)",
                "case_sensitive": "boolean - Case-sensitive search (default false)",
                "file_pattern": "string - Glob pattern for files to search (e.g., '*.py')",
                "file_type": "string - File type for ripgrep (e.g., 'py', 'js', 'ts')",
                "max_results": "integer - Max results to return (default 50)",
                "context_lines": "integer - Lines of context around matches for ripgrep (default 2)",
                "include_hidden": "boolean - Search hidden files/directories (default false)"
            },
            "failure_hints": ["search_dir_not_found", "permission_denied", "search_timeout", "invalid_regex"],
            "searchers": ["ripgrep", "grep", "python"]
        }
    
    def get_examples(self) -> list[dict]:
        """Return example code_search actions."""
        return [
            {
                "query": "def main",
                "file_type": "py",
                "max_results": 20
            },
            {
                "query": "TODO|FIXME",
                "use_regex": True,
                "file_pattern": "*.py"
            },
            {
                "query": "class.*Tool",
                "use_regex": True,
                "search_dir": "src"
            }
        ]
