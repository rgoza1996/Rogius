/**
 * Python Bridge Client
 * 
 * TypeScript client for communicating with the Python FastAPI backend.
 * Wraps all TUI Python functionality for the webapp.
 */

const PYTHON_API_BASE = process.env.NEXT_PUBLIC_PYTHON_API_URL || 'http://127.0.0.1:8000';

// Terminal Types
export interface TerminalExecuteRequest {
  command: string;
  cwd?: string;
  timeout?: number;
}

export interface TerminalExecuteResponse {
  stdout: string;
  stderr: string;
  exit_code: number;
  command: string;
  shell_used: string;
  cwd: string;
}

// Multi-Step Types
export interface MultistepStep {
  id: string;
  description: string;
  command: string;
  status: 'pending' | 'running' | 'completed' | 'error' | 'skipped';
  result?: string;
  error?: string;
}

export interface MultistepCreateRequest {
  goal: string;
  steps: Array<{
    description: string;
    command: string;
  }>;
}

export interface MultistepCreateResponse {
  plan_id: string;
  goal: string;
  steps_count: number;
  status: string;
}

export interface MultistepStatusResponse {
  plan_id: string;
  goal: string;
  status: string;
  current_step: number;
  total_steps: number;
  progress_percentage: number;
  steps: MultistepStep[];
}

// AI Types
export interface AIChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface AIChatRequest {
  messages: AIChatMessage[];
  enable_tools?: boolean;
  stream?: boolean;
}

export interface AIChatResponse {
  content: string;
  tool_calls?: Array<{
    id?: string;
    index: number;
    type: string;
    function: {
      name: string;
      arguments: string;
    };
  }>;
  finish_reason?: string;
}

// TTS Types
export interface TTSRequest {
  input: string;
  voice?: string;
  speed?: number;
}

export interface TTSCheckResponse {
  available: boolean;
  endpoint: string;
  error?: string;
}

// Settings Types
export interface SettingsResponse {
  chat_endpoint: string;
  chat_api_key: string;
  chat_model: string;
  chat_context_length: number;
  tts_endpoint: string;
  tts_api_key: string;
  tts_voice: string;
  auto_play_audio: boolean;
  max_retries: number;
}

// System Info Types
export interface SystemInfoResponse {
  os: string;
  os_version: string;
  architecture: string;
  shell: string;
  hostname: string;
  username: string;
  python_version: string;
  working_directory: string;
  package_manager: string;
  has_sudo: boolean;
  node_version: string;
  docker_version: string;
}

// Chat Types
export interface ChatSession {
  id: string;
  title: string;
  messages: Array<{
    role: 'system' | 'user' | 'assistant';
    content: string;
    messageId?: string;
    branches?: Array<{
      messageId: string;
      content: string;
      timestamp: number;
      subtree: any[];
    }>;
    currentBranchIndex?: number;
    agentExecution?: any;
  }>;
  createdAt: number;
  updatedAt: number;
  userTitled?: boolean;
  userMessageCount?: number;
}

export interface ChatIndexEntry {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
}

export interface ChatListResponse {
  chats: ChatIndexEntry[];
}

export interface StorageInfo {
  location: string;
  chatCount: number;
  totalSizeBytes: number;
  totalSizeKB: number;
}

/**
 * Python Bridge - Main API client
 */
export class PythonBridge {
  private baseUrl: string;

  constructor(baseUrl: string = PYTHON_API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async fetch(path: string, options?: RequestInit): Promise<Response> {
    const url = `${this.baseUrl}${path}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response;
  }

  // Health Check
  async health(): Promise<{ status: string; timestamp: string; version: string }> {
    const response = await this.fetch('/health');
    return response.json();
  }

  // Terminal API
  terminal = {
    execute: async (request: TerminalExecuteRequest): Promise<TerminalExecuteResponse> => {
      const response = await this.fetch('/terminal/execute', {
        method: 'POST',
        body: JSON.stringify(request),
      });
      return response.json();
    },

    history: async (): Promise<{ commands: Array<{
      command: string;
      exit_code: number;
      stdout: string;
      stderr: string;
    }> }> => {
      const response = await this.fetch('/terminal/history');
      return response.json();
    },
  };

  // Multi-Step API
  multistep = {
    create: async (request: MultistepCreateRequest): Promise<MultistepCreateResponse> => {
      const response = await this.fetch('/multistep/create', {
        method: 'POST',
        body: JSON.stringify(request),
      });
      return response.json();
    },

    status: async (): Promise<MultistepStatusResponse | { active_plan: null }> => {
      const response = await this.fetch('/multistep/status');
      return response.json();
    },

    execute: async (): Promise<{
      plan_id: string;
      status: string;
      completed: number;
      total: number;
      percentage: number;
    }> => {
      const response = await this.fetch('/multistep/execute', {
        method: 'POST',
      });
      return response.json();
    },

    executeNext: async (): Promise<{
      current_step: number;
      step_status: string | null;
    }> => {
      const response = await this.fetch('/multistep/execute-next', {
        method: 'POST',
      });
      return response.json();
    },

    executeAgentic: async (request: { goal: string; steps: Array<{description: string; command: string}>; max_iterations?: number }): Promise<{
      plan_id: string;
      goal: string;
      status: string;
      completed: number;
      total: number;
      percentage: number;
      execution_log?: Array<{event: string; step?: number; description?: string; result?: string; error?: string; action?: string; reasoning?: string}>;
      steps?: Array<{
        id: string;
        description: string;
        command: string;
        status: string;
        result?: string;
        error?: string;
      }>;
    }> => {
      const response = await this.fetch('/agents/execute', {
        method: 'POST',
        body: JSON.stringify({ goal: request.goal }),
      });
      return response.json();
    },

    executeAgenticStream: async function* (
      request: { goal: string; steps: Array<{description: string; command: string}>; max_iterations?: number }
    ): AsyncGenerator<
      | { type: 'phase'; phase: string; message?: string }
      | { type: 'start'; goal: string; total_steps: number }
      | { type: 'step_start'; step: number; description: string }
      | { type: 'step_complete'; step: number; result: string; output?: string }
      | { type: 'step_error'; step: number; error: string; output?: string }
      | { type: 'step_warn'; step: number; message: string; output?: string }
      | { type: 'retry'; step: number; attempt: number; hint?: string }
      | { type: 'decision'; action: string; reasoning: string }
      | { type: 'decision_error'; message: string }
      | { type: 'complete'; status: string; completed: number; total: number; percentage: number }
      | { type: 'error'; message: string }
      | { type: 'report'; report: string }
      | { type: 'agent_prompt'; agent: string; from_agent: string; system_prompt: string; user_prompt: string }
      | { type: 'agent_inference_chunk'; agent: string; chunk: string }
      | { type: 'agent_inference'; agent: string; response: string }
    > {
      // Use Next.js proxy to avoid CORS issues
      const response = await fetch('/api/python/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          endpoint: '/multistep/execute-agentic-stream',
          goal: request.goal,
          steps: request.steps || [],
          max_iterations: request.max_iterations || 50,
        }),
      });

      if (!response.ok) {
        const error = await response.text();
        yield { type: 'error', message: error };
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        yield { type: 'error', message: 'No response body' };
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              yield data;
            } catch {
              // Ignore parse errors
            }
          }
        }
      }
    },

    clear: async (): Promise<{ status: string }> => {
      const response = await this.fetch('/multistep/clear', {
        method: 'POST',
      });
      return response.json();
    },

    modify: async (request: { stepIndex?: number; newCommand: string; newDescription?: string }): Promise<{ status: string; step_index: number }> => {
      const response = await this.fetch('/multistep/modify', {
        method: 'POST',
        body: JSON.stringify(request),
      });
      return response.json();
    },

    skip: async (request: { stepIndex?: number }): Promise<{ status: string; step_index: number }> => {
      const response = await this.fetch('/multistep/skip', {
        method: 'POST',
        body: JSON.stringify(request),
      });
      return response.json();
    },

    add: async (request: { afterStepIndex?: number; description: string; command: string }): Promise<{ status: string; insert_index: number }> => {
      const response = await this.fetch('/multistep/add', {
        method: 'POST',
        body: JSON.stringify(request),
      });
      return response.json();
    },
  };

  // AI Chat API
  ai = {
    chat: async (request: AIChatRequest): Promise<AIChatResponse> => {
      const response = await this.fetch('/ai/chat', {
        method: 'POST',
        body: JSON.stringify(request),
      });
      return response.json();
    },

    chatStream: async (
      request: AIChatRequest,
      onChunk: (chunk: Partial<AIChatResponse>) => void,
      onDone?: () => void
    ): Promise<void> => {
      const response = await fetch(`${this.baseUrl}/ai/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              onDone?.();
              return;
            }
            try {
              const chunk = JSON.parse(data);
              onChunk(chunk);
            } catch {
              // Ignore parse errors
            }
          }
        }
      }

      onDone?.();
    },

    models: async (): Promise<{ models: string[]; error?: string }> => {
      const response = await this.fetch('/ai/models');
      return response.json();
    },
  };

  // TTS API
  tts = {
    check: async (): Promise<TTSCheckResponse> => {
      const response = await this.fetch('/tts/check');
      return response.json();
    },

    generateSpeech: async (request: TTSRequest): Promise<Blob> => {
      const response = await fetch(`${this.baseUrl}/tts/speech`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      return response.blob();
    },
  };

  // Settings API
  settings = {
    get: async (): Promise<SettingsResponse> => {
      const response = await this.fetch('/settings');
      return response.json();
    },

    update: async (settings: SettingsResponse): Promise<{ status: string }> => {
      const response = await this.fetch('/settings', {
        method: 'POST',
        body: JSON.stringify(settings),
      });
      return response.json();
    },
  };

  // System Info API
  system = {
    info: async (): Promise<SystemInfoResponse> => {
      const response = await this.fetch('/system/info');
      return response.json();
    },
  };

  // Chat Storage API
  chats = {
    list: async (): Promise<ChatListResponse> => {
      const response = await this.fetch('/chats');
      return response.json();
    },

    get: async (chatId: string): Promise<ChatSession | null> => {
      const response = await fetch(`${this.baseUrl}/chats/${chatId}`, {
        headers: { 'Content-Type': 'application/json' },
      });
      if (!response.ok) {
        if (response.status === 404) return null;
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    },

    save: async (chat: ChatSession): Promise<{ status: string; id: string }> => {
      const response = await this.fetch('/chats', {
        method: 'POST',
        body: JSON.stringify(chat),
      });
      return response.json();
    },

    delete: async (chatId: string): Promise<{ status: string; id: string }> => {
      const response = await fetch(`${this.baseUrl}/chats/${chatId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return response.json();
    },

    clear: async (): Promise<{ status: string; count: number }> => {
      const response = await this.fetch('/chats', {
        method: 'DELETE',
      });
      return response.json();
    },

    storageInfo: async (): Promise<StorageInfo> => {
      const response = await this.fetch('/chats/storage/info');
      return response.json();
    },
  };
}

// Export singleton instance
export const pythonBridge = new PythonBridge();

export default pythonBridge;
