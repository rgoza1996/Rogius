# Prompt: Implement Task Management Tools

## Goal
Add structured task tracking and interactive user prompts to enable better project organization and user interaction, matching Windsurf's todo list and question capabilities.

## Tools to Implement

### 1. `todo_list`
**Purpose**: Create and manage structured task lists with priorities and statuses
**Parameters**:
- `todos` (array, required): List of todo items
  - `content` (string): Task description
  - `status` (enum): 'pending', 'in_progress', or 'completed'
  - `priority` (enum): 'high', 'medium', or 'low'
  - `id` (string): Unique identifier

**Features**:
- Create new todo lists
- Update existing todos
- Mark tasks as completed
- Change priorities
- Reorganize tasks
- Use for organizing complex work

**Status Management**:
- Mark first item as 'in_progress' to indicate current work
- Update tasks as work progresses
- Archive completed todos or delete when done

### 2. `ask_user_question`
**Purpose**: Ask the user a question with predefined options
**Parameters**:
- `question` (string, required): The question to ask
- `options` (array, required): Up to 4 predefined options
  - `label` (string): Short option label
  - `description` (string): Longer explanation of the option
- `allowMultiple` (boolean, required): Allow selecting multiple options

**Rules**:
- Maximum 4 options
- NEVER include "other" as option (user can always provide custom response)
- Use when user needs to make a specific choice
- Not for open-ended questions

**Features**:
- Single or multiple selection
- Descriptive labels and explanations
- Custom response always available
- Modal/panel UI in webapp
- Interactive prompt in TUI

## Implementation Notes

### For Webapp:

```typescript
// Todo List State Management
interface Todo {
  id: string;
  content: string;
  status: 'pending' | 'in_progress' | 'completed';
  priority: 'high' | 'medium' | 'low';
  createdAt: Date;
  updatedAt: Date;
}

interface TodoListState {
  todos: Todo[];
  activeId: string | null;  // Currently in_progress item
}

// UI Components
// 1. TodoListPanel - Sidebar or overlay showing tasks
// 2. TodoItem - Individual task with status indicator
// 3. PriorityBadge - High/Medium/Low indicator
// 4. StatusToggle - Pending/In Progress/Completed

// Add to page.tsx state
const [todos, setTodos] = useState<Todo[]>([]);
const [showTodos, setShowTodos] = useState(false);

// Todo handlers in tool execution
const handleTodoList = (todosData: Todo[]) => {
  setTodos(todosData);
  setShowTodos(true);
  // Highlight in_progress item
  const active = todosData.find(t => t.status === 'in_progress');
  if (active) {
    highlightInUI(active.id);
  }
};
```

```typescript
// Question Dialog
interface QuestionOption {
  label: string;
  description: string;
}

interface QuestionDialogProps {
  question: string;
  options: QuestionOption[];
  allowMultiple: boolean;
  onAnswer: (answer: string | string[]) => void;
  onCustom: (response: string) => void;
}

// Modal implementation
const QuestionModal: React.FC<QuestionDialogProps> = ({
  question,
  options,
  allowMultiple,
  onAnswer,
  onCustom
}) => {
  const [selected, setSelected] = useState<string[]>([]);
  const [customInput, setCustomInput] = useState('');
  
  return (
    <Modal>
      <h3>{question}</h3>
      <div className="options">
        {options.map(opt => (
          <button
            key={opt.label}
            onClick={() => handleSelect(opt.label)}
            className={selected.includes(opt.label) ? 'selected' : ''}
          >
            <strong>{opt.label}</strong>
            <p>{opt.description}</p>
          </button>
        ))}
      </div>
      <input 
        placeholder="Or type custom response..."
        value={customInput}
        onChange={e => setCustomInput(e.target.value)}
      />
    </Modal>
  );
};
```

### For TUI:

```python
# Add to src/tui/ai_client.py
# Implement in src/tui/task_manager.py

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import json
from pathlib import Path

class TodoStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class Priority(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class Todo:
    id: str
    content: str
    status: TodoStatus
    priority: Priority

class TodoManager:
    def __init__(self, storage_path: str = "~/.rogius/todos.json"):
        self.storage_path = Path(storage_path).expanduser()
        self.todos: list[Todo] = []
        self.load()
    
    def load(self):
        if self.storage_path.exists():
            data = json.loads(self.storage_path.read_text())
            self.todos = [Todo(**item) for item in data]
    
    def save(self):
        data = [{"id": t.id, "content": t.content, 
                 "status": t.status.value, "priority": t.priority.value} 
                for t in self.todos]
        self.storage_path.write_text(json.dumps(data, indent=2))
    
    def update(self, todos: list[Todo]):
        self.todos = todos
        self.save()
        self.render()
    
    def render(self):
        # Update TUI display
        from textual.widgets import DataTable
        # Show todo list in dedicated widget
        pass

class QuestionPrompt:
    def __init__(self, question: str, options: list[dict], allow_multiple: bool):
        self.question = question
        self.options = options
        self.allow_multiple = allow_multiple
        self.answer: Optional[str | list[str]] = None
    
    async def ask(self) -> str | list[str]:
        # Display question in TUI
        # Show numbered options
        # Accept selection input
        # Allow custom text input
        pass
```

### Tool Definitions:

```typescript
// Add to TERMINAL_TOOLS in src/lib/api-client.ts
const TASK_TOOLS = [
  {
    type: 'function',
    function: {
      name: 'todo_list',
      description: 'Create, update, or manage a todo list. Use this to organize tasks with different statuses and priorities. Mark the first item as in_progress to indicate current work.',
      parameters: {
        type: 'object',
        properties: {
          todos: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                content: { type: 'string', description: 'Task description' },
                status: { 
                  type: 'string', 
                  enum: ['pending', 'in_progress', 'completed'],
                  description: 'Task status'
                },
                priority: { 
                  type: 'string', 
                  enum: ['high', 'medium', 'low'],
                  description: 'Task priority'
                },
                id: { type: 'string', description: 'Unique identifier' }
              },
              required: ['content', 'status', 'priority', 'id']
            }
          }
        },
        required: ['todos']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'ask_user_question',
      description: 'Ask the user a question with predefined options. Use when the user needs to make a choice between specific options. Never include "other" as an option. Set allowMultiple to true if user should select more than one.',
      parameters: {
        type: 'object',
        properties: {
          question: { type: 'string', description: 'The question to ask' },
          options: {
            type: 'array',
            maxItems: 4,
            items: {
              type: 'object',
              properties: {
                label: { type: 'string', description: 'Short option label' },
                description: { type: 'string', description: 'Longer explanation' }
              },
              required: ['label', 'description']
            }
          },
          allowMultiple: { 
            type: 'boolean', 
            description: 'Allow selecting multiple options' 
          }
        },
        required: ['question', 'options', 'allowMultiple']
      }
    }
  }
];
```

## Use Cases:

### Complex Project Planning:
```
AI: todo_list({
  todos: [
    { id: "1", content: "Analyze requirements", status: "completed", priority: "high" },
    { id: "2", content: "Design database schema", status: "in_progress", priority: "high" },
    { id: "3", content: "Implement API endpoints", status: "pending", priority: "high" },
    { id: "4", content: "Write tests", status: "pending", priority: "medium" },
    { id: "5", content: "Deploy to staging", status: "pending", priority: "low" }
  ]
})
```

### User Decision:
```
AI: ask_user_question({
  question: "Which database should we use for this project?",
  options: [
    { label: "PostgreSQL", description: "Robust relational database with JSON support" },
    { label: "MongoDB", description: "Document-based NoSQL, flexible schema" },
    { label: "SQLite", description: "Lightweight, serverless, good for development" }
  ],
  allowMultiple: false
})
```

### Multi-Select:
```
AI: ask_user_question({
  question: "Which features should we implement first?",
  options: [
    { label: "Authentication", description: "User login and registration" },
    { label: "Dashboard", description: "Main user dashboard view" },
    { label: "API", description: "REST API endpoints" },
    { label: "Settings", description: "User preferences and settings" }
  ],
  allowMultiple: true
})
```

## Integration with Multi-Step Tasks:

```python
# Enhance existing multistep.py with todo integration

class MultiStepPlan:
    def __init__(self, ...):
        self.todos: list[Todo] = []
    
    def sync_with_todos(self):
        """Convert plan steps to todo items"""
        self.todos = [
            Todo(
                id=step.id,
                content=step.description,
                status=TodoStatus.PENDING if step.status == StepStatus.PENDING 
                        else TodoStatus.IN_PROGRESS if step.status == StepStatus.RUNNING
                        else TodoStatus.COMPLETED if step.status == StepStatus.COMPLETED
                        else TodoStatus.PENDING,
                priority=Priority.HIGH if step.is_critical else Priority.MEDIUM
            )
            for step in self.steps
        ]
        return self.todos
```

## Testing Checklist
- [ ] Create new todo list
- [ ] Update todo status
- [ ] Change todo priority
- [ ] Mark in_progress
- [ ] Persistence across restarts
- [ ] Single-select question
- [ ] Multi-select question
- [ ] Custom text response
- [ ] Question with max 4 options
- [ ] Option labels and descriptions
- [ ] UI rendering in webapp
- [ ] TUI interactive prompt
- [ ] Integration with multistep tasks
