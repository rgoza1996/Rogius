export interface ChatMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface ChatCompletionRequest {
  model: string
  messages: ChatMessage[]
  stream?: boolean
  temperature?: number
  max_tokens?: number
}

export interface ChatCompletionResponse {
  id: string
  object: string
  created: number
  model: string
  choices: {
    index: number
    message: ChatMessage
    finish_reason: string
  }[]
}

export interface TTSRequest {
  input: string
  voice?: string
  speed?: number
}

export interface APIConfig {
  chatEndpoint: string
  chatApiKey: string
  chatModel: string
  chatContextLength: number
  ttsEndpoint: string
  ttsApiKey: string
  ttsVoice: string
  ttsModel: string  // Optional model ID for Groq-style TTS (e.g. canopylabs/orpheus-3b)
  systemPrompt: string
  systemPromptEditable: boolean
  autoPlayAudio: boolean
  maxRetries: number
}

// Shell-specific command mappings
const SHELL_INSTRUCTIONS: Record<string, { name: string; forbidden: string; useInstead: string; stringRules?: string }> = {
  powershell: {
    name: 'Windows PowerShell',
    forbidden: 'ls, cat, rm, cp (Unix commands), for /l (CMD syntax), fake cmdlets like Measure-HaikuQuality',
    useInstead: 'Get-ChildItem, Get-Content, Set-Content, New-Item, Remove-Item, Copy-Item, Test-Path',
    stringRules: '- Use double quotes for strings\n- To write newlines: use `r`n in double quotes (NOT \\n)\n- Example: Set-Content -Value "Line1`r`nLine2"'
  },
  bash: {
    name: 'Bash',
    forbidden: 'PowerShell cmdlets like Get-ChildItem, CMD commands like dir',
    useInstead: 'ls, cat, rm, cp, mkdir, touch, chmod, grep, awk, sed',
    stringRules: '- Use single or double quotes for strings\n- Use \\n for newlines in double quotes\n- Example: echo -e "Line1\\nLine2"'
  },
  zsh: {
    name: 'Zsh',
    forbidden: 'PowerShell cmdlets like Get-ChildItem, CMD commands like dir',
    useInstead: 'ls, cat, rm, cp, mkdir, touch, chmod, grep, awk, sed',
    stringRules: '- Use single or double quotes for strings\n- Use \\n for newlines in double quotes\n- Example: echo "Line1\\nLine2"'
  },
  cmd: {
    name: 'Windows CMD',
    forbidden: 'Unix commands (ls, cat, rm), PowerShell cmdlets',
    useInstead: 'dir, type, del, copy, md, rd, echo, findstr',
    stringRules: '- Use double quotes for strings with spaces\n- Use ^ to escape special characters\n- Use & to chain commands'
  },
  sh: {
    name: 'POSIX Shell (sh)',
    forbidden: 'PowerShell cmdlets, Bash-specific features like [[ ]]',
    useInstead: 'ls, cat, rm, cp, mkdir, test, grep, awk',
    stringRules: '- Use basic POSIX features only\n- Use test instead of [[ ]]\n- Example: if [ "$var" = "value" ]; then'
  }
}

/**
 * Get shell-specific instructions based on detected shell
 */
export function getShellInstructions(shell: string): { name: string; forbidden: string; useInstead: string; stringRules: string } {
  const shellLower = shell.toLowerCase()
  
  // Match shell to known types
  let instructions = SHELL_INSTRUCTIONS.powershell // Default to PowerShell
  
  if (shellLower.includes('bash')) {
    instructions = SHELL_INSTRUCTIONS.bash
  } else if (shellLower.includes('zsh')) {
    instructions = SHELL_INSTRUCTIONS.zsh
  } else if (shellLower.includes('cmd') || shellLower.includes('command')) {
    instructions = SHELL_INSTRUCTIONS.cmd
  } else if (shellLower.includes('sh') && !shellLower.includes('bash') && !shellLower.includes('zsh')) {
    instructions = SHELL_INSTRUCTIONS.sh
  }
  
  return {
    name: instructions.name,
    forbidden: instructions.forbidden,
    useInstead: instructions.useInstead,
    stringRules: instructions.stringRules || '- Use standard shell quoting rules'
  }
}

/**
 * Generate a dynamic system prompt based on detected shell and OS
 */
export function generateSystemPrompt(shell: string = 'powershell', os: string = 'windows'): string {
  const instructions = getShellInstructions(shell)
  const osContext = os ? ` on ${os}` : ''
  
  return `You are Rogius, an AI assistant that EXECUTES commands via tools.

CRITICAL: You are using ${instructions.name}${osContext}. Use ONLY ${instructions.name} commands.

NEVER USE: ${instructions.forbidden}

ALWAYS USE: ${instructions.useInstead}

STRING RULES:
${instructions.stringRules}

KEEP COMMANDS SIMPLE - one operation per step. For complex logic, use multiple steps.

For MULTIPLE actions, use start_multistep_task tool.

AVAILABLE TOOLS:
- execute_command: Single command execution ONLY - for one-off commands
- start_multistep_task: Create and execute a complete multi-step plan AUTOMATICALLY

MANDATORY: For ANY request with MULTIPLE actions, you MUST use start_multistep_task.`
}

// Base system prompt (used when system info not yet collected)
const DEFAULT_SYSTEM_PROMPT = generateSystemPrompt('powershell', 'windows')

const DEFAULT_CONFIG: APIConfig = {
  chatEndpoint: 'https://api.openai.com/v1/chat/completions',
  chatApiKey: '',
  chatModel: 'gpt-3.5-turbo',
  chatContextLength: 4096,
  ttsEndpoint: 'http://100.71.89.62:8880/v1/audio/speech',
  ttsApiKey: '',
  ttsVoice: 'af_bella',
  ttsModel: '',
  systemPrompt: DEFAULT_SYSTEM_PROMPT,
  systemPromptEditable: false,
  autoPlayAudio: false,
  maxRetries: 999
}

export function getStoredConfig(): APIConfig {
  // DEPRECATED: Settings now loaded exclusively from Python backend
  // This function returns defaults only; actual settings fetched via pythonBridge.settings.get()
  return DEFAULT_CONFIG
}

export function saveConfig(config: APIConfig): void {
  // DEPRECATED: Settings now saved exclusively to Python backend
  // Use pythonBridge.settings.update() instead
}

// Tool definitions for AI function calling
export const TERMINAL_TOOLS = [
  {
    type: 'function',
    function: {
      name: 'execute_command',
      description: 'Execute a PowerShell command on the Windows machine. TRIGGER: Use this tool IMMEDIATELY for ANY request involving: random numbers, math calculations, file operations, opening apps, running scripts, system info, date/time, process management, or ANY task requiring computation. DO NOT explain you cannot do it - JUST USE THIS TOOL. Examples: "random number" → use this tool with Get-Random; "what time is it" → use this tool with Get-Date; "create a file" → use this tool with New-Item.',
      parameters: {
        type: 'object',
        properties: {
          command: {
            type: 'string',
            description: 'The shell command to execute (e.g., "notepad", "code .", "ls", "dir", "mkdir folder")'
          },
          cwd: {
            type: 'string',
            description: 'Optional working directory (relative to project root)'
          }
        },
        required: ['command']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'open_terminal',
      description: 'Open the terminal panel UI so the user can see terminal output. Use this when showing command results to the user.',
      parameters: {
        type: 'object',
        properties: {}
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'start_multistep_task',
      description: 'Start a multi-step task with a goal and planned steps. CRITICAL: Use this automatically for ANY task that involves multiple actions, sequential operations, or the words "and", "then", "afterwards", "verify". DO NOT ask the user - just plan and execute. Each step should be discrete and verifiable.',
      parameters: {
        type: 'object',
        properties: {
          goal: { type: 'string', description: 'Clear description of the overall task goal' },
          steps: {
            type: 'array',
            description: 'List of steps to execute in order - include ALL steps needed to complete the goal',
            items: {
              type: 'object',
              properties: {
                description: { type: 'string', description: 'What this step does' },
                command: { type: 'string', description: 'Shell command to execute' }
              },
              required: ['description', 'command']
            }
          }
        },
        required: ['goal', 'steps']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'modify_step',
      description: 'Modify a step (usually the current failed step) with a new command. Use this when a step fails and you need to try an alternative approach after investigation.',
      parameters: {
        type: 'object',
        properties: {
          stepIndex: { type: 'number', description: 'Index of step to modify (0-based). If omitted, modifies current step.' },
          newDescription: { type: 'string', description: 'Updated description' },
          newCommand: { type: 'string', description: 'New command to try' }
        },
        required: ['newCommand']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'skip_step',
      description: 'Skip the current or specified step. Use this if a step is optional or cannot be completed but the task can continue.',
      parameters: {
        type: 'object',
        properties: {
          stepIndex: { type: 'number', description: 'Index to skip (0-based). If omitted, skips current step.' }
        }
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'add_step',
      description: 'Add a new step after the current one. Use this when investigation reveals you need an additional diagnostic or preparatory step.',
      parameters: {
        type: 'object',
        properties: {
          afterStepIndex: { type: 'number', description: 'Add after this index (0-based). If omitted, adds after current step.' },
          description: { type: 'string', description: 'What this step does' },
          command: { type: 'string', description: 'Shell command to execute' }
        },
        required: ['description', 'command']
      }
    }
  },
  {
    type: 'function',
    function: {
      name: 'verify_task_completion',
      description: 'Verify that the multi-step task is complete and all objectives are met. Call this after all steps are executed for final validation.',
      parameters: { type: 'object', properties: {} }
    }
  }
]

export interface ToolCall {
  id?: string
  index?: number
  type: 'function'
  function: {
    name?: string
    arguments: string
  }
}

export async function* streamChatCompletion(
  messages: ChatMessage[],
  config: APIConfig,
  enableTools: boolean = false,
  signal?: AbortSignal
): AsyncGenerator<{ content?: string; toolCalls?: ToolCall[] }, void, unknown> {
  const requestBody: any = {
    model: config.chatModel,
    messages,
    stream: true,
    temperature: 0.7,
    max_tokens: config.chatContextLength,
  }
  
  // Add tools if enabled
  if (enableTools) {
    requestBody.tools = TERMINAL_TOOLS
    requestBody.tool_choice = 'auto'
  }
  
  // Build headers - API key is optional
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  
  // Only add Authorization header if API key is provided
  if (config.chatApiKey && config.chatApiKey.trim() !== '') {
    headers['Authorization'] = `Bearer ${config.chatApiKey}`
  }
  
  const response = await fetch(config.chatEndpoint, {
    method: 'POST',
    headers,
    body: JSON.stringify(requestBody),
    signal,
  })

  if (!response.ok) {
    const error = await response.text()
    throw new Error(`API error: ${response.status} - ${error}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data: ')) continue
        
        const data = trimmed.slice(6)
        if (data === '[DONE]') return

        try {
          const parsed = JSON.parse(data)
          console.log('Parsed chunk:', parsed)
          const delta = parsed.choices?.[0]?.delta
          const content = delta?.content
          const toolCalls = delta?.tool_calls
          
          if (content || toolCalls) {
            console.log('Yielding - content:', content, 'toolCalls:', toolCalls)
            yield { content, toolCalls }
          }
        } catch (e) {
          // Ignore parse errors for incomplete chunks
          console.log('Parse error:', e)
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export async function generateSpeech(
  text: string,
  config: APIConfig
): Promise<Blob> {
  try {
    const body: Record<string, unknown> = {
      input: text,
      voice: config.ttsVoice,
      speed: 1.0,
      response_format: 'wav',
    }
    // Include model field for Groq/OpenAI-style TTS
    if (config.ttsModel) {
      body.model = config.ttsModel
    } else if (config.ttsEndpoint.includes('groq.com')) {
      // Groq always needs a model; fall back to voice as model ID
      body.model = config.ttsVoice
    }

    const response = await fetch(config.ttsEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(config.ttsApiKey && { 'Authorization': `Bearer ${config.ttsApiKey}` }),
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const error = await response.text()
      throw new Error(`TTS server error: ${response.status} - ${error}`)
    }

    return response.blob()
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(`TTS connection failed: Cannot reach ${config.ttsEndpoint}. Is KokoroTTS running on the remote machine?`)
    }
    throw error
  }
}

export async function fetchModels(config: APIConfig): Promise<string[]> {
  try {
    const baseUrl = config.chatEndpoint.replace('/chat/completions', '')
    const response = await fetch(`${baseUrl}/models`, {
      method: 'GET',
      headers: {
        ...(config.chatApiKey && { 'Authorization': `Bearer ${config.chatApiKey}` }),
      },
    })

    if (!response.ok) {
      return []
    }

    const data = await response.json()
    return data.data?.map((m: { id: string }) => m.id) || []
  } catch {
    return []
  }
}

