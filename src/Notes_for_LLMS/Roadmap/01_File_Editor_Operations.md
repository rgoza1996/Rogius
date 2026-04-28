# Prompt: Implement File/Editor Operations Tools

## Goal
Add comprehensive file manipulation tools to Rogius that match Windsurf/Cline capabilities. These tools provide direct file API access rather than relying on shell commands.

## Tools to Implement

### 1. `read_file`
**Purpose**: Read file contents with optional line offsets and limits
**Parameters**:
- `file_path` (string, required): Absolute path to file
- `offset` (number, optional): 1-indexed line to start reading from
- `limit` (number, optional): Maximum lines to read

**Features**:
- Return content with line numbers in `cat -n` format
- Truncate lines longer than 2000 characters
- Support images (display visually in webapp, base64 in TUI)
- Handle large files gracefully with pagination

**Output Format**:
```
<file name="/path/to/file" start_line="1" end_line="50" full_length="200">
1  import os
2  import sys
...
</file>
```

### 2. `write_to_file`
**Purpose**: Create new files with full contents
**Parameters**:
- `TargetFile` (string, required): Full absolute path including directory
- `CodeContent` (string, required): File contents to write
- `EmptyFile` (boolean, required): Set to true for empty files

**Requirements**:
- Create parent directories if they don't exist
- NEVER overwrite existing files (fail with error)
- Generate TargetFile parameter FIRST before CodeContent

### 3. `edit`
**Purpose**: Precise single string replacement
**Parameters**:
- `file_path` (string, required): Absolute path to file
- `old_string` (string, required): Text to replace (must be unique in file)
- `new_string` (string, required): Replacement text
- `replace_all` (boolean, optional): Replace all occurrences
- `explanation` (string, required): Description of the change

**Rules**:
- old_string MUST be unique in the file (unless replace_all=true)
- Preserve exact indentation (tabs/spaces) as it appears after the line number prefix
- Include sufficient surrounding context to make old_string unique
- Never output code to user - use edit tool directly

### 4. `multi_edit`
**Purpose**: Multiple edits to a single file atomically
**Parameters**:
- `file_path` (string, required): Absolute path
- `edits` (array, required): List of {old_string, new_string, replace_all?}
- `explanation` (string, required): Description of changes

**Requirements**:
- All edits applied sequentially to the result of the previous edit
- If any edit fails, none are applied (atomic)
- Use for renaming variables across a file (replace_all)
- Keep edits scoped and minimal

### 5. `list_dir`
**Purpose**: List files and directories with metadata
**Parameters**:
- `DirectoryPath` (string, required): Absolute path to directory

**Output**:
- File: relative path and size in bytes
- Directory: relative path and item count (recursive)
- Capped at 50 matches with filtering options
- Skip gitignored files by default

### 6. Jupyter Notebook Support
**Purpose**: Read and edit .ipynb files
**Tools**:
- `read_notebook` - Parse and display cells with IDs and outputs
- `edit_notebook` - Replace cell contents or insert new cells
- Support both `cell_number` (0-indexed) and `cell_id` targeting
- Edit modes: 'replace' or 'insert'

## Implementation Notes

### For Webapp (TypeScript/React):
- Add tool definitions to `src/lib/api-client.ts`
- Implement handlers in `src/app/page.tsx` tool execution section
- Use browser File System Access API where available
- Fallback to API endpoints for server-side file operations

### For TUI (Python):
- Add to `src/tui/ai_client.py` TERMINAL_TOOLS list
- Implement handlers in `src/tui/tui.py` or `src/tui/multistep.py`
- Use standard Python `pathlib` and `os` modules
- Handle Windows/Unix path differences

### Security Considerations:
- Validate file paths (prevent directory traversal)
- Respect .gitignore patterns
- Add allowlist for sensitive directories
- Confirm destructive operations (delete, overwrite)

## Testing Checklist
- [ ] Read file with line numbers
- [ ] Read file with offset and limit
- [ ] Read image files
- [ ] Write new file with directory creation
- [ ] Edit unique string
- [ ] Multi-edit atomicity
- [ ] List directory contents
- [ ] Jupyter notebook read
- [ ] Jupyter notebook edit
- [ ] Error handling for non-existent files
- [ ] Path traversal protection
