'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import type { APIConfig } from '@/lib/api-client'
import { getStoredConfig } from '@/lib/api-client'
import { pythonBridge } from '@/lib/python-bridge'
import {
  ChatSession,
  BranchedMessage,
  createNewChat,
  saveChat,
  getAllChats,
} from '@/lib/chat-storage'

export interface UseChatReturn {
  // State
  currentChat: ChatSession | null
  messages: BranchedMessage[]
  input: string
  isLoading: boolean
  config: APIConfig
  autoScrollEnabled: boolean
  
  // Refs
  messagesRef: React.MutableRefObject<BranchedMessage[]>
  currentChatRef: React.MutableRefObject<ChatSession | null>
  abortControllerRef: React.MutableRefObject<AbortController | null>
  messagesEndRef: React.RefObject<HTMLDivElement>
  textareaRef: React.RefObject<HTMLTextAreaElement>
  
  // Actions
  setCurrentChat: (chat: ChatSession | null) => void
  setMessages: React.Dispatch<React.SetStateAction<BranchedMessage[]>>
  setInput: (input: string) => void
  setIsLoading: (loading: boolean) => void
  setConfig: React.Dispatch<React.SetStateAction<APIConfig>>
  setAutoScrollEnabled: (enabled: boolean) => void
  appendToLastMessage: (content: string) => void
  handleNewChat: () => Promise<ChatSession>
  handleSelectChat: (chat: ChatSession) => void
  handleChatDeleted: (deletedChatId: string) => void
  clearChat: () => void
  showDocumentation: () => void
  stopGeneration: () => void
}

export function useChat(): UseChatReturn {
  const [currentChat, setCurrentChat] = useState<ChatSession | null>(null)
  const [messages, setMessages] = useState<BranchedMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [config, setConfig] = useState<APIConfig>(getStoredConfig())
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true)

  // Ref for synchronous access to messages
  const messagesRef = useRef(messages)
  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

  // Ref for synchronous access to current chat (needed for streaming to check if user switched)
  const currentChatRef = useRef(currentChat)
  useEffect(() => {
    currentChatRef.current = currentChat
  }, [currentChat])

  const messagesEndRef = useRef<HTMLDivElement>(null!)
  const abortControllerRef = useRef<AbortController | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null!)

  // Helper to append content to the last assistant message incrementally
  const appendToLastMessage = useCallback((additionalContent: string) => {
    setMessages(prev => {
      const last = prev[prev.length - 1]
      if (last?.role === 'assistant') {
        return [...prev.slice(0, -1), {
          ...last,
          content: last.content + additionalContent
        }]
      }
      return prev
    })
  }, [])

  // Initialize - load config from Python backend (sole source of truth)
  useEffect(() => {
    const loadConfig = async () => {
      try {
        // Python backend is the ONLY source of truth for settings
        const backendSettings = await pythonBridge.settings.get()
        const backendConfig: APIConfig = {
          ...getStoredConfig(),  // Only for systemPrompt default
          chatEndpoint: backendSettings.chat_endpoint,
          chatApiKey: backendSettings.chat_api_key,
          chatModel: backendSettings.chat_model,
          chatContextLength: backendSettings.chat_context_length,
          ttsEndpoint: backendSettings.tts_endpoint,
          ttsApiKey: backendSettings.tts_api_key,
          ttsVoice: backendSettings.tts_voice,
          autoPlayAudio: backendSettings.auto_play_audio
        }
        setConfig(backendConfig)
        console.log('Loaded config from Python backend:', backendConfig.chatModel)
      } catch (error) {
        console.error('Failed to load settings from Python backend:', error)
        // Keep default config, user will see error when trying to save
      }
    }
    loadConfig()

    // Load chats from file-based storage
    getAllChats().then(chats => {
      if (chats.length > 0) {
        const mostRecent = chats.sort((a, b) => b.updatedAt - a.updatedAt)[0]
        setCurrentChat(mostRecent)
        setMessages(mostRecent.messages)
        // Track as already saved so we don't re-save on init
        lastSavedMessagesRef.current = mostRecent.messages
      } else {
        // No chats exist, create new
        createNewChat().then(newChat => {
          setCurrentChat(newChat)
          setMessages([])
          lastSavedMessagesRef.current = []
        })
      }
    })
  }, [])

  // Auto-scroll to bottom on new messages (only if user is near bottom)
  useEffect(() => {
    if (!autoScrollEnabled) return
    
    // Check if user is near bottom (within 100px)
    const container = messagesEndRef.current?.parentElement
    if (container) {
      const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100
      if (isNearBottom) {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      }
    }
  }, [messages, autoScrollEnabled])

  // Track scroll position to enable/disable auto-scroll
  useEffect(() => {
    const container = messagesEndRef.current?.parentElement
    if (!container) return
    
    const handleScroll = () => {
      const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100
      setAutoScrollEnabled(isNearBottom)
    }
    
    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [])

  // Track last saved messages to detect actual changes vs just selection
  const lastSavedMessagesRef = useRef<BranchedMessage[]>([])

  // Save chat when messages actually change (not just on selection)
  useEffect(() => {
    if (currentChat && messages.length > 0) {
      const lastSaved = lastSavedMessagesRef.current
      // Only save if messages are different from last saved
      const messagesChanged =
        lastSaved.length !== messages.length ||
        JSON.stringify(lastSaved) !== JSON.stringify(messages)

      console.log('[useChat] Save check:', { 
        chatId: currentChat.id, 
        messageCount: messages.length, 
        lastSavedCount: lastSaved.length, 
        messagesChanged 
      })

      if (messagesChanged) {
        const updatedChat: ChatSession = {
          ...currentChat,
          messages: JSON.parse(JSON.stringify(messages)), // Deep clone to ensure clean serialization
          updatedAt: Date.now()
        }
        console.log('[useChat] Saving chat with', messages.length, 'messages')
        saveChat(updatedChat).catch(error => {
          console.error('[useChat] Failed to save chat:', error)
          // Don't throw - saving is best-effort, app should continue working
        })
        lastSavedMessagesRef.current = JSON.parse(JSON.stringify(messages)) // Clone for comparison
      }
    }
  }, [messages, currentChat])

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [input])

  const handleNewChat = useCallback(async (): Promise<ChatSession> => {
    console.log('[handleNewChat] Starting...')
    const newChat = await createNewChat()
    console.log('[handleNewChat] Created new chat:', newChat.id)
    setCurrentChat(newChat)
    setMessages([])
    setInput('')
    // Track empty messages as already saved
    lastSavedMessagesRef.current = []
    console.log('[handleNewChat] State updated, returning')
    return newChat
  }, [])

  const handleSelectChat = useCallback((chat: ChatSession) => {
    // Switch to selected chat - don't abort ongoing inference (it continues in background)
    setCurrentChat(chat)
    setMessages(chat.messages)
    // Track these messages as already saved so we don't re-save and update updatedAt
    lastSavedMessagesRef.current = chat.messages
  }, [])

  const handleChatDeleted = useCallback((deletedChatId: string) => {
    if (currentChat?.id === deletedChatId) {
      setCurrentChat(null)
      setMessages([])
    }
  }, [currentChat])

  const clearChat = useCallback(() => {
    setMessages([])
    // Create new chat asynchronously but don't wait
    createNewChat().then(newChat => {
      setCurrentChat(newChat)
    })
    abortControllerRef.current?.abort()
    setIsLoading(false)
  }, [])

  const showDocumentation = useCallback(() => {
    setCurrentChat(null)
    setMessages([])
    abortControllerRef.current?.abort()
    setIsLoading(false)
  }, [])

  const stopGeneration = useCallback(() => {
    abortControllerRef.current?.abort()
    setIsLoading(false)
  }, [])

  return {
    currentChat,
    messages,
    input,
    isLoading,
    config,
    autoScrollEnabled,
    setAutoScrollEnabled,
    messagesRef,
    currentChatRef,
    abortControllerRef,
    textareaRef,
    messagesEndRef,
    setCurrentChat,
    setMessages,
    setInput,
    setIsLoading,
    setConfig,
    appendToLastMessage,
    handleNewChat,
    handleSelectChat,
    handleChatDeleted,
    clearChat,
    showDocumentation,
    stopGeneration,
  }
}
