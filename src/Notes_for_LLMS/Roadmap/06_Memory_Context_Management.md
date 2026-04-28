# Prompt: Implement Memory & Context Management Tools

## Goal
Add persistent memory system to remember user preferences, project context, and conversation history across sessions, matching Windsurf's memory database capabilities.

## Tools to Implement

### 1. `create_memory`
**Purpose**: Save, update, or delete persistent memories
**Parameters**:
- `Action` (enum, required): 'create', 'update', or 'delete'
- `Title` (string, required for create/update): Descriptive title for the memory
- `Content` (string, required for create/update): Memory content
- `Id` (string, required for update/delete): Existing memory ID
- `Tags` (array, optional for create): Tags for filtering/retrieval (snake_case)
- `CorpusNames` (array, optional for create): Workspace URIs associated with memory
- `UserTriggered` (boolean, optional): True if user explicitly requested this memory

**Memory Types**:
1. **Global Rules** - System-wide rules that always apply
2. **User Preferences** - Explicit user requests to remember
3. **Project Context** - Technical stacks, project structure
4. **Code Snippets** - Important code to remember
5. **Design Patterns** - Architectural decisions
6. **Milestones** - Major features completed

**Features**:
- Semantic similarity matching before creating (update existing if similar)
- Persistent storage across sessions
- Tag-based organization
- Workspace/corpus association
- User-triggered vs AI-generated distinction

### 2. `trajectory_search`
**Purpose**: Search or retrieve previous conversation trajectories
**Parameters**:
- `ID` (string, required): Trajectory ID (cascade ID for conversations)
- `Query` (string, optional): Search string within trajectory (empty = all steps)
- `SearchType` (enum, required): 'cascade' for conversations

**Features**:
- Retrieve chunks from previous conversations
- Score, sort, and filter by relevance
- Maximum 50 chunks returned
- Search within specific conversation history

**Use Cases**:
- Reference previous solutions
- Continue interrupted work
- Learn from past interactions
- Build on prior context

## Implementation Notes

### Storage Backend Options:

**Option 1: SQLite (Simple, Local)**
```python
# Schema
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT,  -- JSON array
    corpus_names TEXT,  -- JSON array
    user_triggered BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    embedding BLOB  -- For semantic search
);

CREATE TABLE trajectories (
    id TEXT PRIMARY KEY,
    type TEXT,  -- 'conversation', 'activity'
    content TEXT,
    timestamp TIMESTAMP
);
```

**Option 2: Vector DB (Pinecone, Weaviate, Chroma)**
- Better semantic search
- Requires external service
- More complex setup

### For Webapp:
```typescript
// Add to src/lib/api-client.ts

// Server API:
// POST /api/memory - Create/update/delete
// GET /api/memory/search - Semantic search
// GET /api/memory/:id - Retrieve specific
// POST /api/trajectory/search - Search conversations

interface Memory {
  id: string;
  title: string;
  content: string;
  tags: string[];
  corpusNames: string[];
  userTriggered: boolean;
  createdAt: Date;
  updatedAt: Date;
}

// Semantic similarity function
async function findSimilarMemory(
  content: string, 
  threshold: number = 0.8
): Promise<Memory | null> {
  // Use embeddings to find similar
}
```

### For TUI:
```python
# Add to src/tui/ai_client.py
# Implement in src/tui/memory.py

import sqlite3
import json
from datetime import datetime
from typing import Optional
import hashlib

class MemoryManager:
    def __init__(self, db_path: str = "~/.rogius/memories.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT,
                    corpus_names TEXT,
                    user_triggered BOOLEAN,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
    
    def create(self, title: str, content: str, tags: list[str] = None, 
               corpus_names: list[str] = None, user_triggered: bool = False) -> str:
        # Check for similar existing memory
        existing = self._find_similar(content)
        if existing:
            return self.update(existing['id'], title=title, content=content)
        
        memory_id = hashlib.md5(f"{title}{datetime.now()}".encode()).hexdigest()
        # Insert new memory
        return memory_id
    
    def update(self, id: str, **kwargs) -> str:
        # Update existing memory
        pass
    
    def delete(self, id: str):
        # Delete memory
        pass
    
    def search(self, query: str, corpus_names: list[str] = None) -> list[dict]:
        # Search memories
        pass
```

### Tool Definitions:

```typescript
// Add to TERMINAL_TOOLS in src/lib/api-client.ts
const MEMORY_TOOLS = [
  {
    type: 'function',
    function: {
      name: 'create_memory',
      description: 'Save important context to a persistent memory database. Before creating, check for semantically related memories and update them instead of duplicating. Use for user preferences, project structure, code snippets, design patterns, and milestones.',
      parameters: {
        type: 'object',
        properties: {
          Action: { 
            type: 'string', 
            enum: ['create', 'update', 'delete'],
            description: 'Action to perform'
          },
          Title: { type: 'string', description: 'Descriptive title (required for create/update)' },
          Content: { type: 'string', description: 'Memory content (required for create/update)' },
          Id: { type: 'string', description: 'Memory ID (required for update/delete)' },
          Tags: { 
            type: 'array', 
            items: { type: 'string' },
            description: 'Tags for filtering (snake_case)'
          },
          CorpusNames: { 
            type: 'array', 
            items: { type: 'string' },
            description: 'Workspace URIs associated'
          },
          UserTriggered: { 
            type: 'boolean', 
            description: 'True if user explicitly requested'
          }
        },
        required: ['Action']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'trajectory_search',
      description: 'Search or retrieve chunks from previous conversation trajectories. Returns scored, sorted, filtered chunks (max 50). Use when user references previous work or @mentions a conversation.',
      parameters: {
        type: 'object',
        properties: {
          ID: { type: 'string', description: 'Trajectory/Conversation ID' },
          Query: { type: 'string', description: 'Search string (empty = all steps)' },
          SearchType: { 
            type: 'string', 
            enum: ['cascade'],
            description: 'Type of trajectory'
          }
        },
        required: ['ID', 'SearchType']
      }
    }
  }
];
```

### Auto-Memory Creation:
```python
# Automatically create memories for:
AUTO_MEMORY_TRIGGERS = {
    'user_preference': r'(always|never|prefer|like|want|remember)\s+(?:to\s+)?(.+)',
    'tech_stack': r'using\s+(React|Vue|Angular|Python|Node|Django|FastAPI)',
    'project_structure': r'project\s+(?:structure|layout|organization)',
    'important_decision': r'(decided|agreed|concluded)\s+(?:that\s+)?(.+)',
}

# On user message, check for auto-memory triggers
# Create memory if match found and user_triggered = False
```

## Use Cases:

### Remember Preferences:
```
User: "Always use 2-space indentation in this project"
AI: create_memory({
  Action: "create",
  Title: "Project Indentation Preference",
  Content: "Use 2-space indentation for all files in this project",
  Tags: ["preference", "formatting", "project"],
  UserTriggered: true
})
```

### Update Existing:
```
User: "Actually, I prefer 4 spaces now"
AI: create_memory({
  Action: "update",
  Id: "existing-memory-id",
  Title: "Project Indentation Preference",
  Content: "Use 4-space indentation for all files in this project",
  Tags: ["preference", "formatting", "project"],
  UserTriggered: true
})
```

### Search Trajectory:
```
User: "What did we do about the auth bug last week?"
AI: trajectory_search({
  ID: "conversation-abc-123",
  Query: "auth bug fix",
  SearchType: "cascade"
})
```

## Testing Checklist
- [ ] Create new memory
- [ ] Update existing memory
- [ ] Delete memory
- [ ] Semantic similarity detection
- [ ] Tag-based filtering
- [ ] Corpus/workspace association
- [ ] Trajectory search
- [ ] Empty query retrieval
- [ ] User-triggered vs auto distinction
- [ ] Memory persistence across restarts
- [ ] Duplicate prevention
