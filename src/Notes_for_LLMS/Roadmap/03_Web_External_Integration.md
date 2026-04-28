# Prompt: Implement Web & External Integration Tools

## Goal
Enable Rogius to access external web resources for research, documentation lookup, and real-time information retrieval, matching Windsurf's web capabilities.

## Tools to Implement

### 1. `search_web`
**Purpose**: Perform web searches to get relevant documents
**Parameters**:
- `query` (string, required): Search query
- `domain` (string, optional): Prioritize results from specific domain

**Features**:
- Return list of relevant web documents
- Support domain prioritization
- Provide document IDs for chunk retrieval
- Respect robots.txt and rate limits

**Use Cases**:
- Research API documentation
- Find solutions to error messages
- Look up library usage examples
- Verify package versions

### 2. `read_url_content`
**Purpose**: Read and parse web page content
**Parameters**:
- `Url` (string, required): HTTP or HTTPS URL

**Features**:
- Fetch accessible internet resources
- Parse HTML to extract readable content
- Handle various content types (HTML, text, JSON)
- Support user approval before fetching (security)
- Truncate very long content

**Workflow**:
1. User provides URL
2. Tool proposes fetch (requires approval)
3. On approval, fetches and returns content
4. Content stored with DocumentId for chunking

**Use Cases**:
- Read documentation pages
- Fetch API schemas
- Read blog posts/tutorials
- Access GitHub raw files

### 3. `view_content_chunk`
**Purpose**: View specific chunks of large web documents
**Parameters**:
- `document_id` (string, required): ID from previous read_url_content
- `position` (number, required): Chunk position to view

**Features**:
- Navigate large documents incrementally
- Must be used after read_url_content
- Allows focused reading of relevant sections

**Use Cases**:
- Read long documentation pages piece by piece
- Navigate large API references
- Review lengthy articles

## Implementation Notes

### For Webapp:
```typescript
// Add to src/lib/api-client.ts
// Implement via server API to avoid CORS:
//   - POST /api/web/search
//   - POST /api/web/fetch (with approval queue)
//   - POST /api/web/chunk

// UI considerations:
// - Show approval dialog for external fetches
// - Display loading state during fetch
// - Cache fetched content
// - Show domain in UI for security transparency
```

### For TUI:
```python
# Add to src/tui/ai_client.py
# Implement in src/tui/web_client.py

# Use aiohttp for async requests
# Implement caching with TTL
# Add approval prompt in TUI interface
# Handle timeouts and retries
```

### Security Model:
1. **Approval Required**: All external fetches need user approval
2. **Domain Filtering**: Configurable allowlist/blocklist
3. **Rate Limiting**: Prevent abuse of external APIs
4. **Privacy**: Don't send sensitive code to external services
5. **Timeout**: Maximum fetch duration (e.g., 30 seconds)

### Configuration:
```json
// rogius.config.json addition
{
  "web": {
    "searchEnabled": true,
    "fetchEnabled": true,
    "requireApproval": true,
    "allowedDomains": ["*"],
    "blockedDomains": ["internal.company.com"],
    "timeoutSeconds": 30,
    "maxContentSize": 1000000
  }
}
```

## Use Cases & Examples

### Error Research:
```
User: "What does 'ECONNREFUSED 127.0.0.1:3000' mean?"
AI: search_web("ECONNREFUSED 127.0.0.1:3000 node.js error")
AI: read_url_content("https://stackoverflow.com/questions/...")
```

### API Documentation:
```
User: "How do I use the Stripe create customer API?"
AI: search_web("Stripe create customer API reference")
AI: read_url_content("https://stripe.com/docs/api/customers/create")
```

### Package Research:
```
User: "What's the latest version of React?"
AI: search_web("React latest version npm")
AI: read_url_content("https://www.npmjs.com/package/react")
```

## Testing Checklist
- [ ] Basic web search
- [ ] Domain-filtered search
- [ ] Fetch HTML page
- [ ] Fetch JSON API
- [ ] Chunk navigation
- [ ] User approval flow
- [ ] Timeout handling
- [ ] Rate limit handling
- [ ] CORS handling (webapp)
- [ ] Error handling (404, 500, etc.)
- [ ] Large document chunking
- [ ] Content type detection
- [ ] Security approval prompt
