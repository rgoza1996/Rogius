/**
 * Python Backend Chat Storage
 * 
 * Chat sessions are stored exclusively via the Python backend API.
 * Storage location: ~/.rogius/chats/
 * 
 * NOTE: Python backend must be running for chat history to work.
 */

import { ChatMessage } from './api-client'

// Health check for Python backend
async function checkPythonHealth(): Promise<boolean> {
  try {
    const response = await fetch('/api/python/health', { method: 'GET' })
    return response.ok
  } catch {
    return false
  }
}

// Agent tracking for multi-agent workflow
export type AgentPhase = 'investigation' | 'planning' | 'execution' | 'verification' | 'reporting' | 'complete' | 'error'

export interface AgentStatus {
  name: string
  phase: AgentPhase
  status: 'pending' | 'running' | 'completed' | 'error'
  description?: string
  timestamp: number
  // New fields for prompt/inference visibility
  systemPrompt?: string
  userPrompt?: string
  fromAgent?: string
  inference?: string
  isExpanded?: boolean
}

export interface AgentExecutionState {
  goal: string
  agents: AgentStatus[]
  currentAgentIndex: number
  totalSteps: number
  completedSteps: number
  isExpanded: boolean
  log: string[]
}

// Extended message with branching support
export interface BranchedMessage extends ChatMessage {
  messageId: string
  branches?: Branch[]
  currentBranchIndex?: number
  agentExecution?: AgentExecutionState
}

export interface Branch {
  messageId: string
  content: string
  timestamp: number
  subtree: BranchedMessage[]
}

export interface ChatSession {
  id: string
  title: string
  messages: BranchedMessage[]
  createdAt: number
  updatedAt: number
  userTitled?: boolean
  userMessageCount?: number
}

export interface StorageInfo {
  location: string
  chatCount: number
  totalSizeBytes: number
  totalSizeKB: number
}

export function generateChatId(): string {
  return `chat-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

export function generateMessageId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

export function createBranchedMessage(
  role: 'user' | 'assistant' | 'system',
  content: string
): BranchedMessage {
  return {
    role,
    content,
    messageId: generateMessageId(),
    branches: [],
    currentBranchIndex: -1
  }
}

export function generateChatTitle(messages: ChatMessage[]): string {
  const firstUserMessage = messages.find(m => m.role === 'user')
  if (firstUserMessage) {
    const content = firstUserMessage.content
    return content.length > 30 ? content.substring(0, 30) + '...' : content
  }
  return 'New Chat'
}

// Generate AI-based chat title from conversation context
export async function generateAITitle(
  messages: BranchedMessage[],
  chatConfig: { chatEndpoint: string; chatApiKey?: string; chatModel: string },
  systemPrompt: string
): Promise<string | null> {
  if (messages.length === 0) return null

  // Get last few messages for context (up to 4 messages to save tokens)
  const context = messages.slice(-4)
  const conversation = context.map(m => {
    const role = m.role === 'user' ? 'User' : 'AI'
    return `${role}: ${m.content.substring(0, 200)}${m.content.length > 200 ? '...' : ''}`
  }).join('\n\n')

  const titlePrompt = `${systemPrompt}

Based on the following conversation, generate a concise 2-5 word title that captures the main topic. The title should be descriptive but brief. Respond with ONLY the title, nothing else.

Conversation:
${conversation}

Title:`

  try {
    const response = await fetch(chatConfig.chatEndpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(chatConfig.chatApiKey ? { 'Authorization': `Bearer ${chatConfig.chatApiKey}` } : {})
      },
      body: JSON.stringify({
        model: chatConfig.chatModel,
        messages: [
          { role: 'system', content: titlePrompt }
        ],
        temperature: 0.3,
        max_tokens: 20
      })
    })

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`)
    }

    const data = await response.json()
    const title = data.choices?.[0]?.message?.content?.trim()

    if (title) {
      // Clean up title (remove quotes, limit length)
      const cleaned = title
        .replace(/^[\"'\'"]+|[\"'\'"]+$/g, '')
        .replace(/\n/g, ' ')
        .trim()
        .substring(0, 50)
      return cleaned || null
    }
    return null
  } catch (error) {
    console.error('Failed to generate AI title:', error)
    return null
  }
}

// Safe JSON serializer that handles non-serializable values
function safeStringify(obj: unknown): string {
  return JSON.stringify(obj, (key, value) => {
    // Handle special cases
    if (value === undefined) return null
    if (value instanceof Date) return value.toISOString()
    if (typeof value === 'function') return undefined
    // Handle potential circular references by checking for DOM nodes or window objects
    if (value && typeof value === 'object') {
      if (value.constructor && (
        value.constructor.name === 'Window' ||
        value.constructor.name === 'Document' ||
        value.constructor.name === 'Element' ||
        value.constructor.name === 'HTMLElement'
      )) {
        return undefined
      }
    }
    return value
  })
}

// Save a chat to the Python backend
export async function saveChat(chat: ChatSession): Promise<void> {
  // Check if we should trigger renamer
  checkAndTriggerRenamer(chat)
  
  const updatedChat = {
    ...chat,
    updatedAt: Date.now()
  }
  
  let body: string
  try {
    body = safeStringify(updatedChat)
  } catch (error) {
    console.error('[saveChat] JSON serialization failed:', error)
    console.error('[saveChat] Chat that failed:', {
      id: updatedChat.id,
      title: updatedChat.title,
      messageCount: updatedChat.messages?.length
    })
    throw new Error('Failed to serialize chat data')
  }
  
  // Check Python backend health first
  const isHealthy = await checkPythonHealth()
  if (!isHealthy) {
    throw new Error('Python backend is not running. Please start it first.')
  }

  try {
    const response = await fetch('/api/python/chats', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error('[saveChat] Server error:', response.status, errorText)
      throw new Error(`Failed to save chat: ${response.status} ${errorText}`)
    }
  } catch (error) {
    console.error('[saveChat] Fetch error:', error)
    // Log the chat data that failed (without messages to avoid huge logs)
    console.error('[saveChat] Failed chat:', {
      id: updatedChat.id,
      title: updatedChat.title,
      messageCount: updatedChat.messages?.length,
      createdAt: updatedChat.createdAt,
      updatedAt: updatedChat.updatedAt
    })
    throw error
  }
}

// Toggle chat eligibility for renamer
export async function toggleChatEligibility(chatId: string, eligible: boolean): Promise<void> {
  try {
    await fetch('/api/python/renamer/toggle-eligibility', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId, eligible })
    })
  } catch (error) {
    console.error('Failed to toggle chat eligibility:', error)
    throw error
  }
}

// Manually trigger renamer for a chat
export async function triggerRenamer(chatId: string): Promise<void> {
  try {
    // First make sure chat is eligible
    await toggleChatEligibility(chatId, true)
    // Then enqueue it
    await notifyRenamerEnqueue(chatId)
  } catch (error) {
    console.error('Failed to trigger renamer:', error)
    throw error
  }
}

// Get all chats from Python backend
export async function getAllChats(): Promise<ChatSession[]> {
  // Check Python backend health first
  const isHealthy = await checkPythonHealth()
  if (!isHealthy) {
    throw new Error('Python backend is not running. Please start it first.')
  }

  const response = await fetch('/api/python/chats')
  
  if (!response.ok) {
    throw new Error('Failed to fetch chats')
  }
  
  const data = await response.json()
  const chats: ChatSession[] = []
  
  for (const entry of data.chats || []) {
    const chat = await getChat(entry.id)
    if (chat) {
      chats.push(chat)
    }
  }
  
  return chats
}

// Get a specific chat by ID
export async function getChat(chatId: string): Promise<ChatSession | null> {
  const response = await fetch(`/api/python/chats?id=${chatId}`)
  
  if (!response.ok) {
    return null
  }
  
  try {
    return await response.json()
  } catch {
    return null
  }
}

// Delete a chat
export async function deleteChat(chatId: string): Promise<void> {
  const response = await fetch(`/api/python/chats?id=${chatId}`, {
    method: 'DELETE'
  })
  
  if (!response.ok) {
    throw new Error('Failed to delete chat')
  }
}

// Clear all chats
export async function clearAllChats(): Promise<void> {
  const response = await fetch('/api/python/chats', {
    method: 'DELETE'
  })
  
  if (!response.ok) {
    throw new Error('Failed to clear chats')
  }
}

// Create a new chat
export async function createNewChat(): Promise<ChatSession> {
  const newChat: ChatSession = {
    id: generateChatId(),
    title: 'New Chat',
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
    userTitled: false,
    userMessageCount: 0
  }
  
  await saveChat(newChat)
  return newChat
}

// Get storage info
export async function getStorageInfo(): Promise<StorageInfo | null> {
  const response = await fetch('/api/python/chats/storage')
  
  if (!response.ok) {
    throw new Error('Failed to get storage info')
  }
  
  try {
    return await response.json()
  } catch {
    return null
  }
}

// Update chat title (marks as user-titled to disable AI titling)
export async function updateChatTitle(chatId: string, title: string): Promise<void> {
  const chat = await getChat(chatId)
  if (chat) {
    const updated = { ...chat, title, userTitled: true, updatedAt: Date.now() }
    await saveChat(updated)
    // Also notify renamer to dequeue this chat
    await notifyRenamerDequeue(chatId)
  }
}

// Notify renamer to dequeue a chat (when user manually titles)
async function notifyRenamerDequeue(chatId: string): Promise<void> {
  try {
    await fetch('/api/python/renamer/dequeue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId })
    })
  } catch (error) {
    console.error('Failed to notify renamer dequeue:', error)
  }
}

// Notify renamer to enqueue a chat
async function notifyRenamerEnqueue(chatId: string): Promise<void> {
  try {
    const response = await fetch('/api/python/renamer/enqueue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ chat_id: chatId })
    })
    if (response.ok) {
      console.log(`[Renamer] Chat ${chatId} enqueued for auto-titling`)
    }
  } catch (error) {
    console.error('Failed to notify renamer enqueue:', error)
  }
}

// Count user messages and trigger renamer if count is multiple of 5
function checkAndTriggerRenamer(chat: ChatSession): void {
  // Count user messages
  const userMessageCount = chat.messages.filter(m => m.role === 'user').length
  
  // Update the count on the chat
  chat.userMessageCount = userMessageCount
  
  // If chat is not user-titled and count is multiple of 5 (and >= 5), enqueue it
  if (!chat.userTitled && userMessageCount >= 5 && userMessageCount % 5 === 0) {
    console.log(`[Renamer] Chat ${chat.id} has ${userMessageCount} prompts, adding to queue`)
    notifyRenamerEnqueue(chat.id)
  }
}
