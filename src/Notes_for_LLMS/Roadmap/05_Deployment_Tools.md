# Prompt: Implement Deployment Tools

## Goal
Enable Rogius to deploy web applications directly to hosting providers like Netlify, matching Windsurf's one-click deployment capability.

## Tools to Implement

### 1. `deploy_web_app`
**Purpose**: Deploy a JavaScript web application to a deployment provider
**Parameters**:
- `ProjectPath` (string, required): Full absolute path to web application
- `Framework` (enum, optional): Framework type for build optimization
  - Options: eleventy, angular, astro, create-react-app, gatsby, gridsome, grunt, hexo, hugo, hydrogen, jekyll, middleman, mkdocs, nextjs, nuxtjs, remix, sveltekit, svelte
- `ProjectId` (string, optional): Existing project ID for re-deploys (empty for new sites)
- `Subdomain` (string, optional): Subdomain for new sites (must be unique)

**Rules**:
- Site does not need to be pre-built (source files only required)
- For existing sites: use ProjectId from deployment config
- For new sites: leave ProjectId empty, provide unique Subdomain
- Framework helps optimize build settings

**Features**:
- Automatic build detection and execution
- Framework-specific optimizations
- Deployment status tracking
- URL generation for deployed site

### 2. `check_deploy_status`
**Purpose**: Check deployment status and determine if build succeeded
**Parameters**:
- `WindsurfDeploymentId` (string, required): The deployment ID from deploy_web_app

**Important Notes**:
- Only run when explicitly asked by user
- Must only run after deploy_web_app
- This is the Windsurf deployment ID, NOT project_id

**Features**:
- Returns build status (running, succeeded, failed)
- Checks if application has been claimed
- Provides deployment URL if successful
- Shows error logs if build failed

### 3. `read_deployment_config`
**Purpose**: Read deployment configuration to check if app is ready to deploy
**Parameters**:
- `ProjectPath` (string, required): Full absolute project path

**Features**:
- Checks for required files (package.json, netlify.toml, etc.)
- Determines if application is deployment-ready
- Identifies missing configuration
- Returns existing ProjectId if available

**Returns**:
- Ready status: true/false
- Missing files list
- Existing project configuration
- Framework detection result

## Implementation Notes

### For Webapp:
```typescript
// Add to src/lib/api-client.ts tool definitions

// Server API endpoints needed:
// POST /api/deploy - Initiate deployment
// GET /api/deploy/status/:id - Check deployment status
// GET /api/deploy/config - Read deployment config

// Implementation steps:
// 1. User calls deploy_web_app
// 2. Backend validates project structure
// 3. Backend triggers build (or uses pre-built files)
// 4. Backend deploys to Netlify (or other provider)
// 5. Returns deployment ID for status checking
// 6. User can check status with check_deploy_status
```

### For TUI:
```python
# Add to src/tui/ai_client.py
# Implement in src/tui/deploy.py

# Since TUI can't deploy directly from terminal,
# provide options:
# 1. Generate deployment scripts
# 2. Open deployment URL in browser
# 3. Guide user through CLI deployment

class DeploymentManager:
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.config_file = self.project_path / '.deployment.json'
    
    def check_ready(self) -> DeploymentConfig:
        # Check for package.json, build scripts, etc.
        pass
    
    def generate_netlify_toml(self):
        # Create netlify.toml if missing
        pass
    
    def get_deploy_instructions(self) -> str:
        # Return manual deployment steps
        pass
```

### Netlify Integration:
```toml
# netlify.toml configuration
template = "nextjs"  # or detected framework

[build]
  command = "npm run build"
  publish = "dist"

[build.environment]
  NODE_VERSION = "20"
```

```typescript
// Netlify API integration
interface NetlifyDeployConfig {
  site_id?: string;
  dir: string;
  functions?: string;
  prod?: boolean;
  draft?: boolean;
  message?: string;
}

// Deployment steps:
// 1. Create site (if new) or get existing
// 2. Upload files or trigger git-based build
// 3. Monitor build progress
// 4. Return deploy URL
```

### Tool Definitions:

```typescript
// Add to TERMINAL_TOOLS in src/lib/api-client.ts
const DEPLOYMENT_TOOLS = [
  {
    type: 'function',
    function: {
      name: 'deploy_web_app',
      description: 'Deploy a JavaScript web application to Netlify. Site does not need to be built - only source files required. Ensure all missing files are created before deploying. Use ProjectId for re-deploys to existing sites.',
      parameters: {
        type: 'object',
        properties: {
          ProjectPath: { type: 'string', description: 'Full absolute project path' },
          Framework: { 
            type: 'string', 
            enum: ['eleventy', 'angular', 'astro', 'create-react-app', 'gatsby', 'gridsome', 'grunt', 'hexo', 'hugo', 'hydrogen', 'jekyll', 'middleman', 'mkdocs', 'nextjs', 'nuxtjs', 'remix', 'sveltekit', 'svelte'],
            description: 'Framework for build optimization'
          },
          ProjectId: { type: 'string', description: 'Existing project ID for re-deploys. Leave empty for new sites.' },
          Subdomain: { type: 'string', description: 'Subdomain for new sites. Must be unique. Leave empty for re-deploys.' }
        },
        required: ['ProjectPath']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'check_deploy_status',
      description: 'Check the status of a deployment using its deployment ID. Only run when explicitly asked by the user after a deploy_web_app call.',
      parameters: {
        type: 'object',
        properties: {
          WindsurfDeploymentId: { type: 'string', description: 'The Windsurf deployment ID (not project_id)' }
        },
        required: ['WindsurfDeploymentId']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'read_deployment_config',
      description: 'Read deployment configuration for a web application to determine if it is ready to be deployed. Should be used before deploy_web_app.',
      parameters: {
        type: 'object',
        properties: {
          ProjectPath: { type: 'string', description: 'Full absolute project path' }
        },
        required: ['ProjectPath']
      }
    }
  }
];
```

## Use Cases:

### Deploy New Site:
```
User: "Deploy my React app"
AI: read_deployment_config({ ProjectPath: "/home/user/myapp" })
AI: // Detects create-react-app, missing netlify.toml
AI: // Creates netlify.toml
AI: deploy_web_app({ 
  ProjectPath: "/home/user/myapp", 
  Framework: "create-react-app",
  Subdomain: "my-awesome-app"
})
```

### Re-deploy Existing:
```
User: "Update my deployed site"
AI: read_deployment_config({ ProjectPath: "/home/user/myapp" })
AI: // Finds existing ProjectId
AI: deploy_web_app({ 
  ProjectPath: "/home/user/myapp", 
  Framework: "nextjs",
  ProjectId: "abc-123-def"
})
```

### Check Status:
```
User: "Is my deployment done?"
AI: check_deploy_status({ WindsurfDeploymentId: "deploy-xyz-789" })
```

## Testing Checklist
- [ ] Detect project framework
- [ ] Check deployment readiness
- [ ] Create missing config files
- [ ] Deploy new site
- [ ] Re-deploy existing site
- [ ] Check deployment status
- [ ] Handle build failures
- [ ] Show deployment URL
- [ ] Handle framework detection
- [ ] TUI deployment guidance
- [ ] Environment variable handling
