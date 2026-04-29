# TUI vs Webapp Feature Parity Checklist

## Core Features

| Feature | Webapp | TUI | Status | Notes |
|---------|--------|-----|--------|-------|
| **Chat Interface** | | | | |
| Send/receive messages | ✅ | ✅ | ✅ Parity | Both support streaming |
| Message history | ✅ | ✅ | ✅ Parity | Webapp: localStorage, TUI: in-memory |
| Chat sessions/sidebar | ✅ | ❌ | ⚠️ TUI Gap | TUI: Single session only |
| Branching conversations | ✅ | ❌ | ⚠️ TUI Gap | Webapp has message branching |
| Edit & resend messages | ✅ | ❌ | ⚠️ TUI Gap | TUI: No inline editing |
| **AI Integration** | | | | |
| OpenAI-compatible API | ✅ | ✅ | ✅ Parity | Both support streaming |
| Tool calling | ✅ | ✅ | ✅ Parity | All 8 tools implemented in TUI |
| System prompt | ✅ | ✅ | ✅ Parity | Both configurable |
| Multiple model support | ✅ | ✅ | ✅ Parity | Both support model selection |
| **Terminal Integration** | | | | |
| Execute PowerShell commands | ✅ | ✅ | ✅ Parity | Webapp: /api/terminal, TUI: subprocess |
| Command history | ✅ | ✅ | ✅ Parity | Both track executed commands |
| CWD tracking | ✅ | ✅ | ✅ Parity | Both track working directory |
| Output display | ✅ | ✅ | ✅ Parity | Both show stdout/stderr |
| **Multi-Step Tasks** | | | | |
| start_multistep_task | ✅ | ✅ | ✅ Parity | Both support plan creation |
| execute_next_step | ✅ | ✅ | ✅ Parity | Both execute sequentially |
| modify_step | ✅ | ✅ | ✅ Parity | Both support step modification |
| skip_step | ✅ | ✅ | ✅ Parity | Both support skipping |
| add_step | ✅ | ✅ | ✅ Parity | Both support adding steps |
| verify_task_completion | ✅ | ✅ | ✅ Parity | Both support verification |
| Auto-execution | ✅ | ✅ | ✅ Parity | Both auto-execute with retry |
| Plan visualization | ✅ | ✅ | ✅ Parity | TUI: PlanWidget, Webapp: inline |
| Progress tracking | ✅ | ✅ | ✅ Parity | Both show progress bars |
| **Settings & Config** | | | | |
| API endpoint config | ✅ | ✅ | ✅ Parity | Both configurable |
| API key storage | ✅ | ✅ | ✅ Parity | Both support optional keys |
| Model selection | ✅ | ✅ | ✅ Parity | Both support |
| System prompt | ✅ | ✅ | ✅ Parity | Both editable |
| Settings persistence | ✅ | ✅ | ✅ Parity | Webapp: localStorage, TUI: JSON file |
| TTS configuration | ✅ | ✅ | ✅ Parity | Both support KokoroTTS |
| **Text-to-Speech** | | | | |
| TTS generation | ✅ | ❌ | ⚠️ TUI Gap | TUI: Not yet implemented |
| Auto-play audio | ✅ | ❌ | ⚠️ TUI Gap | TUI: Not yet implemented |
| Voice selection | ✅ | ❌ | ⚠️ TUI Gap | TUI: Not yet implemented |
| Audio playback | ✅ | ❌ | ⚠️ TUI Gap | TUI: Would need audio library |
| **UI/UX** | | | | |
| Responsive design | ✅ | ✅ | ✅ Parity | Both adapt to terminal/gui |
| Keyboard shortcuts | ✅ | ✅ | ✅ Parity | Both have shortcuts |
| Dark theme | ✅ | ✅ | ✅ Parity | Both dark by default |
| Mobile support | ✅ | ❌ | ⚠️ N/A | TUI: Terminal only |

## Tool Calling Support

Both TUI and webapp support the same 8 tools for agentic multi-step tasks:

1. ✅ `execute_command` - Execute terminal commands
2. ✅ `open_terminal` - Show terminal panel
3. ✅ `start_multistep_task` - Create multi-step plan
4. ✅ `execute_next_step` - Execute next step
5. ✅ `modify_step` - Modify a step
6. ✅ `skip_step` - Skip a step
7. ✅ `add_step` - Add a new step
8. ✅ `verify_task_completion` - Verify task completion

## Keyboard Shortcuts

| Shortcut | Webapp | TUI | Action |
|----------|--------|-----|--------|
| Ctrl+S | ✅ | ✅ | Open settings |
| Ctrl+Q | ✅ | ✅ | Quit |
| Ctrl+C | ✅ | ✅ | Cancel operation |
| Ctrl+P | ❌ | ✅ | Focus plan widget |
| Ctrl+N | ❌ | ✅ | Execute next step |
| Enter | ✅ | ✅ | Send message |

## Summary

### ✅ Full Parity (11 features)
- Chat interface core
- AI integration (API, tools, streaming)
- Terminal integration
- Multi-step task execution
- Settings persistence
- Keyboard shortcuts

### ⚠️ TUI Gaps (6 features)
- Chat sessions/sidebar (single session only)
- Message branching
- Inline message editing
- TTS generation & playback
- Audio auto-play

### 🔧 Implementation Quality
- **TUI**: All core multi-step functionality working, tested modules
- **Webapp**: All features working, fixed build issues

## Testing Status

### TUI Components Tested ✅
- [x] multistep.py - Plan creation, execution, progress tracking
- [x] ai_client.py - Streaming, tool parsing
- [x] settings.py - Save/load persistence
- [x] tui.py - Integration, imports, syntax

### Webapp Components Tested ✅
- [x] Terminal API - Type fix applied
- [x] Build - Successful with exclusions
- [x] Multi-step tools - Implemented in page.tsx

## Recommendations

### Priority 1 (Core Functionality) - Complete ✅
All core multi-step agentic task functionality is now at parity between TUI and webapp.

### Priority 2 (Quality of Life) - Optional
1. Add TTS to TUI using a Python audio library (pygame, playsound)
2. Add chat sessions to TUI (save/load multiple conversations)
3. Add message branching to TUI (non-essential)

### Priority 3 (Nice to Have)
1. Remote machine SSH integration for TUI
2. Additional themes for TUI
3. Message search in both

## Conclusion

The TUI and webapp now have **functional parity for multi-step agentic tasks**. The core workflow (AI chat → tool calling → multi-step execution → verification) works identically in both environments.

Key achievement: The TUI now supports the same sophisticated multi-step agentic workflow as the webapp, including:
- Automatic plan creation
- Sequential step execution
- Step modification on failure
- Auto-retry with LLM assistance
- Progress visualization
- Verification
