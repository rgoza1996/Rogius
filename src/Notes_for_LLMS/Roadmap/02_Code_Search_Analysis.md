# Prompt: Implement Code Search & Analysis Tools

## Goal
Add powerful code search capabilities to enable AI-powered codebase exploration, matching Windsurf's "Fast Context" subagent and grep-based search.

## Tools to Implement

### 1. `grep_search`
**Purpose**: Ripgrep-based text search across files
**Parameters**:
- `Query` (string, required): Search term or regex pattern
- `SearchPath` (string, required): Directory or file to search
- `CaseSensitive` (boolean, optional): Default false
- `FixedStrings` (boolean, optional): Treat as literal string, not regex
- `Includes` (array, optional): Glob patterns to filter (e.g., "*.ts", "!**/node_modules/*")
- `MatchPerLine` (boolean, optional): Show surrounding context with matches

**Features**:
- Optimized for large codebases
- Skip hidden files and respect .gitignore by default
- Support regex patterns (treat Query as regex by default)
- Return file paths and line numbers
- Limit results to prevent output overflow

**Use Cases**:
- Find function definitions
- Locate where variables are used
- Search for specific error messages
- Find imports/references

### 2. `find_by_name`
**Purpose**: File discovery by name patterns
**Parameters**:
- `SearchDirectory` (string, required): Directory to search
- `Pattern` (string, required): Glob pattern (e.g., "*.tsx", "test_*")
- `Extensions` (array, optional): File extensions to include (without dots)
- `Excludes` (array, optional): Glob patterns to exclude
- `FullPath` (boolean, optional): Match against full path, not just filename
- `Type` (enum, optional): 'file', 'directory', or 'any'
- `MaxDepth` (number, optional): Maximum directory depth

**Features**:
- Smart case matching
- Skip gitignored files
- Capped at 50 matches
- Return type, size (files), or item count (directories)

**Use Cases**:
- Find all React components
- Locate test files
- Discover configuration files
- List specific directory types

### 3. `code_search` (Fast Context Subagent)
**Purpose**: AI-powered codebase exploration using parallel search
**Parameters**:
- `search_term` (string, required): Natural language query about what to find
- `search_folder_absolute_uri` (string, required): Absolute path to search root

**Behavior**:
- Runs parallel grep and readfile calls
- Locates relevant line ranges and files
- Returns scored, sorted, filtered results
- Maximum 50 chunks returned
- Handles multi-repo workspaces

**Use Cases**:
- "Find authentication request handlers"
- "Locate the bug in feed page redirects"
- "Find tokenizer implementation"
- "Discover API route handlers"

**Implementation Notes**:
- Use for initial codebase exploration before specific grep/file reads
- Results may need verification
- Combine with read_file for detailed examination

## Implementation Notes

### For Webapp:
- Use Web Worker for grep operations to avoid blocking UI
- Implement caching for search results
- Add search history
- Progressive results loading

### For TUI:
- Use Python `re` module for regex search
- Consider `ripgrep` binary if available for performance
- Implement async search with progress indicators
- Cache search indexes

### Integration Points:
```typescript
// Add to src/lib/api-client.ts tool definitions
// Add handlers in src/app/page.tsx
// Implement server API routes:
//   - POST /api/search/grep
//   - POST /api/search/find
//   - POST /api/search/code (subagent)
```

```python
# Add to src/tui/ai_client.py
# Implement in src/tui/search.py or tui.py
# Use asyncio for parallel file operations
```

## Security Considerations:
- Respect .gitignore and .rogiusignore patterns
- Limit search scope to project directory
- Prevent searches outside workspace
- Rate limit search operations

## Testing Checklist
- [ ] Basic text search
- [ ] Regex pattern search
- [ ] Case-sensitive search
- [ ] Literal string search (FixedStrings)
- [ ] Glob pattern filtering
- [ ] Match with context (MatchPerLine)
- [ ] Find files by name pattern
- [ ] Find by extension
- [ ] Exclude patterns
- [ ] Max depth limiting
- [ ] Code search subagent for complex queries
- [ ] Empty/no results handling
- [ ] Performance with large codebases
