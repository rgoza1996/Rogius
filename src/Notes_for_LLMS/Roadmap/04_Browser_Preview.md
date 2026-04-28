# Prompt: Implement Browser Preview Tool

## Goal
Add live browser preview capability for web development, enabling users to interact with their web applications and see visual output from the AI's perspective.

## Tool to Implement

### `browser_preview`
**Purpose**: Spin up a browser preview for a running web server
**Parameters**:
- `Name` (string, required): 3-5 word title-cased name (e.g., 'Personal Website', 'API Dashboard')
- `Url` (string, required): Full URL with scheme, domain, and port (e.g., 'http://localhost:8080')

**Format Requirements**:
- Name: Title-cased, 3-5 words, simple string (no markdown, no "Title:" prefix)
- Url: Must contain scheme (http:// or https://), domain (localhost or IP), and port (:8080)
- No path in URL (just origin)

**Features**:
- Launch browser preview window/panel
- Show console logs from the web app
- Display network requests
- Capture and show JavaScript errors
- Allow user interaction with the preview
- Provide visual feedback to AI

**Behavior**:
1. Validates web server is running at specified URL
2. Opens browser preview (iframe or native browser)
3. Establishes connection for console log streaming
4. Provides interactive interface for user
5. AI can reference visual state in responses

## Implementation Notes

### For Webapp:
```typescript
// Add to src/lib/api-client.ts tool definitions

// Implementation approach:
// 1. Check if server is running (fetch with timeout)
// 2. Open preview panel in UI
// 3. Use iframe for web preview
// 4. Capture console logs via postMessage or proxy

interface BrowserPreviewPanelProps {
  name: string;
  url: string;
  onConsoleLog: (log: ConsoleLog) => void;
  onError: (error: Error) => void;
}

// Console log types
type ConsoleLog = {
  type: 'log' | 'warn' | 'error' | 'info';
  message: string;
  timestamp: number;
  stack?: string;
};
```

### UI Components Needed:
1. **Preview Panel**: Resizable iframe container
2. **Console Drawer**: Toggleable console logs
3. **URL Bar**: Display current preview URL
4. **Refresh Button**: Reload preview
5. **Device Toggle**: Desktop/mobile view modes

### For TUI:
```python
# Add to src/tui/ai_client.py
# Implement in src/tui/browser_preview.py

# TUI approach:
# - Open system default browser
# - Or use terminal-based browser (lynx, w3m) for text mode
# - Stream console logs via WebSocket or polling
# - Show preview status in TUI widget

class BrowserPreview:
    def __init__(self, name: str, url: str):
        self.name = name
        self.url = url
        self.console_logs = []
        self.is_open = False
    
    async def open(self):
        # Validate server running
        # Open browser
        # Start log collection
        pass
    
    def get_console_logs(self) -> list[ConsoleLog]:
        return self.console_logs
```

### Integration with Existing Dev Servers:
- Detect if Next.js, Vite, etc. is already running
- Use existing dev server URL if available
- Auto-suggest common ports (3000, 5173, 8080, etc.)
- Support custom server configurations

### Console Log Capture:

**For Webapp (Iframe)**:
```typescript
// Inject script to capture console
const captureScript = `
  (function() {
    const originalLog = console.log;
    console.log = function(...args) {
      window.parent.postMessage({
        type: 'console',
        level: 'log',
        message: args.map(a => String(a)).join(' ')
      }, '*');
      originalLog.apply(console, args);
    };
    // Similar for warn, error, info
  })();
`;
```

**For TUI (Puppeteer/Playwright)**:
```python
# Use Playwright for headless browser with console capture
from playwright.async_api import async_playwright

async def capture_preview(url: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        page.on("console", lambda msg: print(f"Console: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Error: {err}"))
        
        await page.goto(url)
```

## Tool Definition:

```typescript
// Add to TERMINAL_TOOLS in src/lib/api-client.ts
{
  type: 'function',
  function: {
    name: 'browser_preview',
    description: 'Open a browser preview for a web server. Provides console logs and visual feedback. Use this when the user is developing a web application and needs to see or interact with the UI.',
    parameters: {
      type: 'object',
      properties: {
        Name: {
          type: 'string',
          description: 'Short 3-5 word title-cased name for the preview (e.g., "Personal Website")'
        },
        Url: {
          type: 'string',
          description: 'Full URL with scheme, domain, and port (e.g., "http://localhost:3000")'
        }
      },
      required: ['Name', 'Url']
    }
  }
}
```

## Use Cases:

### Web Development:
```
User: "Run my Next.js app and show me the preview"
AI: execute_command("npm run dev")
AI: browser_preview({ Name: "Next.js App", Url: "http://localhost:3000" })
```

### API Testing:
```
User: "Start the API server and open Swagger UI"
AI: execute_command("python -m uvicorn main:app --reload")
AI: browser_preview({ Name: "API Docs", Url: "http://localhost:8000/docs" })
```

### Visual Debugging:
```
User: "Why isn't my button showing?"
AI: browser_preview({ Name: "Debug View", Url: "http://localhost:5173" })
AI: // Checks console logs, sees CSS error
```

## Testing Checklist
- [ ] Preview panel opens correctly
- [ ] URL validation (scheme, domain, port)
- [ ] Server running detection
- [ ] Console log capture
- [ ] Error capture
- [ ] Refresh/reload functionality
- [ ] Mobile/desktop toggle
- [ ] Iframe sandbox security
- [ ] TUI browser opening
- [ ] Headless browser capture
- [ ] Multiple preview management
- [ ] Preview close/cleanup
