'use client'

import {
  Bot,
  Terminal,
  Settings,
  RotateCcw,
  Volume2,
  MessageSquare,
  GitBranch,
  Copy,
  ArrowLeftRight,
  HardDrive,
  Server,
  Code2,
  Sparkles,
  Zap,
  Shield,
  Keyboard,
} from 'lucide-react'

export function Documentation() {
  return (
    <div className="flex flex-col items-start justify-start h-full p-8 overflow-y-auto">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 rounded-xl bg-primary">
            <Bot className="w-8 h-8 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Rogius</h1>
            <p className="text-sm text-muted-foreground">Agentic AI Development Assistant</p>
          </div>
        </div>

        {/* What is Rogius */}
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
            What is Rogius?
          </h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Rogius is an <strong>agentic AI assistant</strong> designed for software development. 
            Unlike traditional chatbots that only provide text responses, Rogius can take actions 
            directly on your system—executing commands, managing files, and performing multi-step 
            tasks autonomously. It combines the conversational interface of an AI assistant with 
            the capabilities of a development tool.
          </p>
        </div>

        {/* Core Capabilities */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-primary" />
            Core Capabilities
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="p-3 rounded-lg bg-muted/50 border border-border">
              <div className="flex items-center gap-2 mb-1">
                <Terminal className="w-4 h-4 text-primary" />
                <span className="font-medium text-sm">Terminal Commands</span>
              </div>
              <p className="text-xs text-muted-foreground">Execute shell commands in PowerShell or Bash with real-time output capture</p>
            </div>
            <div className="p-3 rounded-lg bg-muted/50 border border-border">
              <div className="flex items-center gap-2 mb-1">
                <Code2 className="w-4 h-4 text-primary" />
                <span className="font-medium text-sm">File Operations</span>
              </div>
              <p className="text-xs text-muted-foreground">Read, write, edit, and analyze files in your workspace</p>
            </div>
            <div className="p-3 rounded-lg bg-muted/50 border border-border">
              <div className="flex items-center gap-2 mb-1">
                <RotateCcw className="w-4 h-4 text-primary" />
                <span className="font-medium text-sm">Multi-Step Tasks</span>
              </div>
              <p className="text-xs text-muted-foreground">Plan and execute complex workflows with autonomous decision-making</p>
            </div>
            <div className="p-3 rounded-lg bg-muted/50 border border-border">
              <div className="flex items-center gap-2 mb-1">
                <Volume2 className="w-4 h-4 text-primary" />
                <span className="font-medium text-sm">Text-to-Speech</span>
              </div>
              <p className="text-xs text-muted-foreground">AI-generated voice responses using KokoroTTS (optional)</p>
            </div>
            <div className="p-3 rounded-lg bg-muted/50 border border-border sm:col-span-2">
              <div className="flex items-center gap-2 mb-1">
                <Bot className="w-4 h-4 text-primary" />
                <span className="font-medium text-sm">Multi-Agent Workflow</span>
              </div>
              <p className="text-xs text-muted-foreground">5 specialized agents (Investigator, Planner, Executor, Verifier) work together autonomously on complex tasks</p>
            </div>
          </div>
        </div>

        {/* Architecture */}
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Server className="w-4 h-4 text-primary" />
            Architecture
          </h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Rogius runs as two integrated components:
          </p>
          <ul className="text-sm text-muted-foreground space-y-1.5 list-disc list-inside">
            <li>
              <strong>Next.js Webapp</strong> — The React-based UI you&apos;re using now, 
              handling chat interface, message branching, and settings
            </li>
            <li>
              <strong>Python Backend</strong> — A FastAPI server that executes system commands, 
              collects environment info, and provides tool capabilities
            </li>
          </ul>
          <p className="text-sm text-muted-foreground leading-relaxed mt-2">
            Chat history is stored in <code className="px-1 py-0.5 bg-muted rounded text-xs">~/.rogius/chats/</code> 
            and shared across all browser ports (3000, 3001, etc.). The Python backend runs on 
            port 8000 by default (configurable via PYTHON_API_URL env var).
          </p>
        </div>

        {/* Multi-Agent System */}
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Bot className="w-4 h-4 text-primary" />
            Multi-Agent System
          </h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Rogius uses a <strong>coordinated multi-agent architecture</strong> for complex tasks:
          </p>
          <ul className="text-sm text-muted-foreground space-y-1.5 list-disc list-inside">
            <li>
              <strong>Investigator:</strong> Probes your environment to gather context about files, structure, and system state
            </li>
            <li>
              <strong>Planner:</strong> Creates a step-by-step execution plan based on investigation findings
            </li>
            <li>
              <strong>Executor:</strong> Generates and runs terminal commands to implement each plan step
            </li>
            <li>
              <strong>Verifier:</strong> QA tests the results and can trigger replanning if issues are found
            </li>
            <li>
              <strong>Rogius (Main):</strong> Orchestrates the workflow and manages agent handoffs
            </li>
            <li>
              <strong>Navigator (Optional):</strong> Handles web research and information gathering when external knowledge is needed
            </li>
          </ul>
          <p className="text-sm text-muted-foreground leading-relaxed mt-2">
            The Agent Tracker UI shows real-time progress, agent states, and execution logs. 
            Click any agent to view its system prompts, inputs, and LLM inferences.
          </p>
        </div>

        {/* Message Branching System */}
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-primary" />
            Message Branching
          </h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Unlike linear chat histories, Rogius uses a <strong>branching model</strong> similar to Git:
          </p>
          <ul className="text-sm text-muted-foreground space-y-1.5 list-disc list-inside">
            <li>
              <strong>Edit & Branch:</strong> Edit any message to create an alternate conversation path
            </li>
            <li>
              <strong>Regenerate:</strong> Click the rotate icon on assistant messages to get fresh responses
            </li>
            <li>
              <strong>Navigate Versions:</strong> Use arrow buttons on branched messages to switch between versions
            </li>
            <li>
              <strong>Split Copy:</strong> Left half of copy button copies current branch, right half copies all branches
            </li>
          </ul>
        </div>

        {/* Keyboard Shortcuts */}
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Keyboard className="w-4 h-4 text-primary" />
            Keyboard Shortcuts
          </h2>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">New Chat</span>
              <kbd className="px-2 py-0.5 bg-muted rounded text-xs">Ctrl+N</kbd>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">Toggle Sidebar</span>
              <kbd className="px-2 py-0.5 bg-muted rounded text-xs">Ctrl+B</kbd>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">Settings</span>
              <kbd className="px-2 py-0.5 bg-muted rounded text-xs">Ctrl+,</kbd>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">Focus Input</span>
              <kbd className="px-2 py-0.5 bg-muted rounded text-xs">/</kbd>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">Send Message</span>
              <kbd className="px-2 py-0.5 bg-muted rounded text-xs">Enter</kbd>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">New Line</span>
              <kbd className="px-2 py-0.5 bg-muted rounded text-xs">Shift+Enter</kbd>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">Stop TTS</span>
              <kbd className="px-2 py-0.5 bg-muted rounded text-xs">Escape</kbd>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">Restart Backend</span>
              <kbd className="px-2 py-0.5 bg-muted rounded text-xs">Shift+Click Server</kbd>
            </div>
          </div>
        </div>

        {/* Quick Start */}
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Zap className="w-4 h-4 text-primary" />
            Quick Start
          </h2>
          <ol className="text-sm text-muted-foreground space-y-1.5 list-decimal list-inside">
            <li>Type a message and press Enter to start a conversation</li>
            <li>Ask Rogius to execute commands: <em>&quot;Run npm install in the backend folder&quot;</em></li>
            <li>Request file operations: <em>&quot;Create a new React component called Button&quot;</em></li>
            <li>Enable TTS in Settings for voice responses (requires KokoroTTS)</li>
            <li>Configure your AI endpoint in Settings (OpenAI-compatible API required)</li>
            <li>Start the Python backend by clicking the server icon in the header (Shift+Click to restart)</li>
          </ol>
        </div>

        {/* Available Tools */}
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Code2 className="w-4 h-4 text-primary" />
            Available AI Tools
          </h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Rogius can automatically invoke these tools based on your requests:
          </p>
          <div className="grid grid-cols-1 gap-2 text-sm">
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">execute_command</span>
              <span className="text-xs text-muted-foreground">Run shell commands (PowerShell/Bash)</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">open_terminal</span>
              <span className="text-xs text-muted-foreground">Show terminal panel UI</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">start_multistep_task</span>
              <span className="text-xs text-muted-foreground">Begin a planned multi-step workflow</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">execute_next_step</span>
              <span className="text-xs text-muted-foreground">Run the next step in active plan</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">modify_step</span>
              <span className="text-xs text-muted-foreground">Change a step after failure</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">skip_step</span>
              <span className="text-xs text-muted-foreground">Skip optional/failed steps</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">add_step</span>
              <span className="text-xs text-muted-foreground">Insert diagnostic steps mid-workflow</span>
            </div>
            <div className="flex items-center justify-between p-2 rounded bg-muted/30">
              <span className="text-muted-foreground">verify_task_completion</span>
              <span className="text-xs text-muted-foreground">Validate all objectives are met</span>
            </div>
          </div>
        </div>

        {/* Settings */}
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Settings className="w-4 h-4 text-primary" />
            Settings
          </h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Configure Rogius via the Settings modal (Ctrl+,). Four tabs are available:
          </p>
          <ul className="text-sm text-muted-foreground space-y-1.5 list-disc list-inside">
            <li>
              <strong>Chat API:</strong> Configure OpenAI-compatible endpoint, API key, model selection, and max tokens
            </li>
            <li>
              <strong>Text-to-Speech:</strong> Set up KokoroTTS endpoint, voice selection, and auto-play options
            </li>
            <li>
              <strong>System Info:</strong> View collected system information (OS, shell, installed tools). Toggle system prompt editing.
            </li>
            <li>
              <strong>Data:</strong> Export, import, or clear all chat history. View storage diagnostics.
            </li>
          </ul>
        </div>

        {/* Security & Privacy */}
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Shield className="w-4 h-4 text-primary" />
            Security & Privacy
          </h2>
          <ul className="text-sm text-muted-foreground space-y-1.5 list-disc list-inside">
            <li>All chat history is stored <strong>locally</strong> on your machine</li>
            <li>API keys are saved in browser localStorage (never sent to our servers)</li>
            <li>Terminal commands require explicit confirmation for destructive operations</li>
            <li>Python backend only binds to localhost (127.0.0.1) by default</li>
          </ul>
        </div>

        {/* Pro Tips */}
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-primary" />
            Pro Tips
          </h2>
          <ul className="text-sm text-muted-foreground space-y-1.5 list-disc list-inside">
            <li>Use the terminal dropdown in the header to view command execution history</li>
            <li>Click the server icon to start/stop the Python backend when needed</li>
            <li>Edit your previous messages to refine prompts without losing context</li>
            <li>Double-click chat titles in the sidebar to rename them</li>
            <li>Use the / key to quickly focus the chat input from anywhere</li>
            <li>Shift+Click the server icon in the header to restart the Python backend</li>
            <li>Export/import your chats from the Data tab in Settings for backup or transfer</li>
            <li>Code blocks support syntax highlighting and copy-to-clipboard</li>
            <li>Click the Agent Tracker in chat to expand and inspect each agent&apos;s prompts and reasoning</li>
            <li>Complex requests automatically trigger the multi-agent workflow for better results</li>
          </ul>
        </div>

        {/* Getting Help */}
        <div className="p-4 rounded-lg bg-primary/5 border border-primary/20">
          <p className="text-sm text-foreground">
            <strong>Need help?</strong> Rogius works best with clear, specific requests. 
            Be explicit about what you want to achieve, and don&apos;t hesitate to edit 
            your messages to refine your requests. The AI will use available tools 
            to help you get things done.
          </p>
        </div>
      </div>
    </div>
  )
}
