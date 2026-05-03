'use client'

import { useMemo } from 'react'
import {
  Send,
  Settings,
  Trash2,
  Volume2,
  VolumeX,
  Square,
  Bot,
  User,
  Loader2,
  MessageSquare,
  RotateCcw,
  Clipboard,
  Check,
  Edit3,
  ChevronLeft,
  ChevronRight,
  Terminal,
  ChevronDown,
  CheckCircle2,
  XCircle,
  Server,
  ServerOff,
  BookOpen,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ChatMessage } from '@/lib/api-client'
import { generateSystemPrompt } from '@/lib/api-client'
import { SettingsModal } from '@/components/settings-modal'
import { ChatSidebar } from '@/components/chat-sidebar'
import { Documentation } from '@/components/documentation'
import { AgentTracker } from '@/components/agent-tracker'
import { MessageContent } from '@/components/message-content'
import { useTerminal, type TerminalCommand } from '@/tools/terminal'
import {
  createBranchedMessage,
  generateMessageId,
  generateAITitle,
  saveChat,
  type BranchedMessage,
  type ChatSession,
} from '@/lib/chat-storage'
import { useChat, useStreaming, useTTS, useBranching, useUIState, usePythonServer, useKokoroServer } from './hooks'

export default function ChatPage() {
  // Terminal hook (external)
  const terminal = useTerminal()

  // Custom hooks
  const chat = useChat()
  const tts = useTTS()
  const branching = useBranching()
  const ui = useUIState()
  const pythonServer = usePythonServer()
  const kokoroServer = useKokoroServer()
  const { streamResponse } = useStreaming(
    {
      config: chat.config,
      setMessages: chat.setMessages,
      setIsLoading: chat.setIsLoading,
      abortControllerRef: chat.abortControllerRef,
      currentChat: chat.currentChat,
      currentChatRef: chat.currentChatRef,
    },
    { executeCommand: terminal.executeCommand }
  )

  // Cache combined system prompt with system info - dynamically generated based on shell
  const combinedSystemPrompt = useMemo(() => {
    // Use detected shell from system info, fallback to PowerShell
    const shell = terminal.systemInfo?.shell || 'powershell'
    const os = terminal.systemInfo?.os || 'windows'
    
    // Generate dynamic system prompt based on actual shell
    const basePrompt = terminal.systemInfo?.collected
      ? generateSystemPrompt(shell, os)
      : chat.config.systemPrompt // Fallback to default if system info not collected
    
    // Append additional system info context
    const systemInfoContext = terminal.systemInfo?.collected
      ? `\n\nSYSTEM INFO (collected at startup):\n- OS: ${terminal.systemInfo.os}\n- Kernel: ${terminal.systemInfo.kernel}\n- Arch: ${terminal.systemInfo.arch}\n- User: ${terminal.systemInfo.user}\n- Shell: ${terminal.systemInfo.shell}\n- Package Manager: ${terminal.systemInfo.packageManager}\n- Has Sudo: ${terminal.systemInfo.hasSudo}\n- Python: ${terminal.systemInfo.pythonVersion}\n- Node: ${terminal.systemInfo.nodeVersion}\n- Docker: ${terminal.systemInfo.dockerVersion}`
      : ''
    
    return basePrompt + systemInfoContext
  }, [chat.config.systemPrompt, terminal.systemInfo])

  
  // Get full conversation context - all messages in the current chat view
  // This ensures both the LLM and copy-to-clipboard get the complete context
  const getCurrentBranchPath = (messages: BranchedMessage[]): BranchedMessage[] => {
    return messages
  }

  // Check if we should generate AI title (after 1st, 6th, 11th, etc. user message)
  const shouldGenerateTitle = (userMessageCount: number): boolean => {
    // After first prompt, then every 5th prompt (6, 11, 16, 21...)
    return userMessageCount === 1 || (userMessageCount > 1 && (userMessageCount - 1) % 5 === 0)
  }

  // Generate AI title and update chat if appropriate
  const maybeGenerateAITitle = async (
    messages: BranchedMessage[],
    currentChat: ChatSession | null
  ) => {
    if (!currentChat || currentChat.userTitled) return

    // Count user messages in current branch
    const branchPath = getCurrentBranchPath(messages)
    const userMessageCount = branchPath.filter(m => m.role === 'user').length

    if (!shouldGenerateTitle(userMessageCount)) return

    // Generate AI title
    const title = await generateAITitle(
      branchPath,
      {
        chatEndpoint: chat.config.chatEndpoint,
        chatApiKey: chat.config.chatApiKey,
        chatModel: chat.config.chatModel
      },
      chat.config.systemPrompt
    )

    if (title) {
      const updatedChat: ChatSession = {
        ...currentChat,
        title,
        userMessageCount,
        updatedAt: Date.now()
      }
      // Only update current chat state if user hasn't switched away
      if (chat.currentChat?.id === currentChat.id) {
        chat.setCurrentChat(updatedChat)
      }
      await saveChat(updatedChat)
    } else {
      // Still update userMessageCount even if title generation failed
      const updatedChat: ChatSession = {
        ...currentChat,
        userMessageCount,
        updatedAt: Date.now()
      }
      // Only update current chat state if user hasn't switched away
      if (chat.currentChat?.id === currentChat.id) {
        chat.setCurrentChat(updatedChat)
      }
    }
  }

  // Generate response wrapper
  const generateResponse = async (currentMessages: BranchedMessage[]) => {
    const branchPath = getCurrentBranchPath(currentMessages)
    const apiMessages: ChatMessage[] = [
      { role: 'system', content: combinedSystemPrompt },
      ...branchPath.map(m => ({ role: m.role, content: m.content }))
    ]

    const result = await streamResponse(apiMessages, currentMessages)

    if (result && chat.config.autoPlayAudio && result.content) {
      tts.speakMessage(result.content, currentMessages.length, chat.config.ttsVoice)
    }

    // Generate AI title if needed (after response is complete)
    if (result) {
      // Get final messages from state after stream completes
      const finalMessages = [...currentMessages, result.assistantMessage]
      maybeGenerateAITitle(finalMessages, chat.currentChat)
    }

    return result
  }

  const handleSubmit = async () => {
    if (!chat.input.trim() || chat.isLoading) return

    let currentChatSession = chat.currentChat
    if (!currentChatSession) {
      currentChatSession = await chat.handleNewChat()
    }

    const userMessage = createBranchedMessage('user', chat.input.trim())
    const newMessages = [...chat.messages, userMessage]
    chat.setMessages(newMessages)
    chat.setInput('')

    // Only send current branch path to API, not all branches
    const branchPath = getCurrentBranchPath(newMessages)
    const apiMessages: ChatMessage[] = [
      { role: 'system', content: combinedSystemPrompt },
      ...branchPath.map(m => ({ role: m.role, content: m.content }))
    ]

    const result = await streamResponse(apiMessages, newMessages)

    if (result && chat.config.autoPlayAudio && result.content) {
      tts.speakMessage(result.content, newMessages.length, chat.config.ttsVoice)
    }

    // Generate AI title if needed
    if (result) {
      const finalMessages = [...newMessages, result.assistantMessage]
      maybeGenerateAITitle(finalMessages, chat.currentChat)
    }
  }

  const resendMessage = async (content: string, messageIndex: number) => {
    const targetMessage = chat.messages[messageIndex]
    if (!targetMessage) return

    if (targetMessage.role === 'assistant') {
      // Regenerating an assistant response - create a branch ON the assistant message itself
      // This allows switching between different AI responses to the same prompt
      const subtree = chat.messages.slice(messageIndex + 1)
      
      // Create new branch for the current assistant response
      const newBranch = {
        messageId: targetMessage.messageId,
        content: targetMessage.content,
        timestamp: Date.now(),
        subtree: [...subtree]
      }

      const updatedMessages = [...chat.messages]
      const existingBranches = targetMessage.branches || []

      if (existingBranches.length === 0) {
        // First branch - save original as branch, new response will be current version
        const newMessageId = generateMessageId()
        updatedMessages[messageIndex] = {
          ...targetMessage,
          content: '', // Clear current content for new response (will be filled by streaming)
          messageId: newMessageId,
          branches: [newBranch], // Just the original, new response goes to current version
          currentBranchIndex: -1 // Use current version slot for new response
        }
      } else {
        // Add new branch to existing branches - only save current response
        // The new response will fill message.content as the "current" version
        const savedBranch = {
          messageId: targetMessage.messageId,
          content: targetMessage.content,
          timestamp: Date.now(),
          subtree: []
        }
        const newMessageId = generateMessageId()
        updatedMessages[messageIndex] = {
          ...targetMessage,
          content: '', // Clear current content for new response (will be filled by streaming)
          messageId: newMessageId,
          branches: [...existingBranches, savedBranch], // Just add the saved branch
          currentBranchIndex: -1 // Use current version slot for new response
        }
      }

      // Remove subsequent messages since we branched
      const truncatedMessages = updatedMessages.slice(0, messageIndex + 1)
      chat.setMessages(truncatedMessages)

      // Generate fresh response - this will fill the content
      await generateResponse(truncatedMessages)
    } else {
      // For user messages, create a branch with the edited content
      const subtree = chat.messages.slice(messageIndex + 1)
      const newBranch = {
        messageId: targetMessage.messageId,
        content: targetMessage.content,
        timestamp: Date.now(),
        subtree: [...subtree]
      }

      const updatedMessages = [...chat.messages]
      const existingBranches = targetMessage.branches || []

      if (existingBranches.length === 0) {
        // First branch - save original as branch, new version will be current
        const newMessageId = generateMessageId()
        const newContentBranch = {
          messageId: newMessageId,
          content: content.trim(),
          timestamp: Date.now(),
          subtree: []
        }
        updatedMessages[messageIndex] = {
          ...targetMessage,
          content: content.trim(),
          messageId: newMessageId,
          branches: [newBranch, newContentBranch],
          currentBranchIndex: 1
        }
      } else {
        // Add new branch to existing branches
        updatedMessages[messageIndex] = {
          ...targetMessage,
          content: content.trim(),
          messageId: generateMessageId(),
          branches: [...existingBranches, newBranch],
          currentBranchIndex: existingBranches.length
        }
      }

      // Remove subsequent messages since we branched
      const truncatedMessages = updatedMessages.slice(0, messageIndex + 1)
      chat.setMessages(truncatedMessages)
      await generateResponse(truncatedMessages)
    }
  }

  const handleNewChat = async () => {
    console.log('[page handleNewChat] Button clicked, calling chat.handleNewChat...')
    await chat.handleNewChat()
    console.log('[page handleNewChat] chat.handleNewChat completed')
    tts.stopSpeaking()
    ui.closeSidebar()
  }

  const handleSelectChat = (chatSession: ChatSession) => {
    chat.handleSelectChat(chatSession)
    tts.stopSpeaking()
    ui.closeSidebar()
  }

  const handleChatDeleted = (deletedChatId: string) => {
    chat.handleChatDeleted(deletedChatId)
  }

  const clearChat = () => {
    chat.clearChat()
    tts.stopSpeaking()
  }

  const saveEdit = async (messageIndex: number) => {
    await branching.saveEdit(
      messageIndex,
      chat.messages,
      chat.setMessages,
      generateResponse
    )
  }

  const switchBranch = (messageIndex: number, branchIndex: number) => {
    branching.switchBranch(messageIndex, branchIndex, chat.messages, chat.setMessages)
  }

  const copyToClipboard = (messageId: string, content: string) => {
    branching.copyToClipboard(messageId, content)
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <ChatSidebar
        currentChatId={chat.currentChat?.id || null}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
        onChatDeleted={handleChatDeleted}
        isOpen={ui.sidebarOpen}
        onToggle={ui.toggleSidebar}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
          <div className="flex items-center gap-2 lg:ml-0 ml-12">
            <div className={cn("p-2 rounded-lg bg-primary", chat.isLoading && "animate-pulse")}>
              <Bot className="w-5 h-5 text-primary-foreground" />
            </div>
            <h1 className="text-lg font-semibold">Rogius</h1>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={clearChat}
              className="p-2 rounded-lg hover:bg-muted transition-colors"
              title="New Chat"
            >
              <Trash2 className="w-5 h-5 text-muted-foreground" />
            </button>
            {/* Terminal Dropdown */}
            <div className="relative" ref={ui.terminalDropdownRef}>
              <button
                onClick={ui.toggleTerminalDropdown}
                className={cn(
                  "p-2 rounded-lg hover:bg-muted transition-colors flex items-center gap-1",
                  terminal.isExecuting && "text-primary animate-pulse"
                )}
                title="Terminal Sessions"
              >
                <Terminal className={cn(
                  "w-5 h-5",
                  terminal.isExecuting ? "text-primary" : "text-muted-foreground"
                )} />
                {terminal.commands.length > 0 && (
                  <span className="text-xs bg-primary text-primary-foreground px-1.5 py-0.5 rounded-full min-w-[1.25rem] text-center">
                    {terminal.commands.length}
                  </span>
                )}
                <ChevronDown className="w-3 h-3 text-muted-foreground" />
              </button>
              
              {ui.terminalDropdownOpen && (
                <div className="absolute right-0 top-full mt-2 w-80 bg-background border border-border rounded-lg shadow-xl z-50 overflow-hidden">
                  <div className="p-3 border-b border-border bg-muted/50">
                    <h3 className="text-sm font-medium">Terminal Sessions</h3>
                    <p className="text-xs text-muted-foreground">
                      {terminal.isExecuting ? 'Command running...' : `${terminal.commands.length} commands executed`}
                    </p>
                  </div>
                  
                  <div className="max-h-64 overflow-y-auto">
                    {terminal.commands.length === 0 ? (
                      <div className="p-4 text-center text-sm text-muted-foreground">
                        No commands executed yet
                      </div>
                    ) : (
                      <div className="divide-y divide-border">
                        {terminal.commands.slice().reverse().map((cmd: TerminalCommand) => (
                          <div key={cmd.id} className="p-3 hover:bg-muted/50 transition-colors group">
                            <div className="flex items-center gap-2">
                              {cmd.status === 'running' ? (
                                <Loader2 className="w-4 h-4 text-primary animate-spin" />
                              ) : cmd.status === 'completed' ? (
                                <CheckCircle2 className="w-4 h-4 text-green-500" />
                              ) : (
                                <XCircle className="w-4 h-4 text-destructive" />
                              )}
                              <code className="text-xs font-mono truncate flex-1">{cmd.command}</code>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  const fullOutput = `$ ${cmd.command}\nCWD: ${cmd.cwd}\nExit: ${cmd.exitCode}\n\nSTDOUT:\n${cmd.stdout || '(no output)'}\n\nSTDERR:\n${cmd.stderr || '(no errors)'}`
                                  navigator.clipboard.writeText(fullOutput)
                                }}
                                className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-muted transition-opacity"
                                title="Copy full output"
                              >
                                <Clipboard className="w-3 h-3 text-muted-foreground" />
                              </button>
                            </div>
                            {cmd.status !== 'running' && (
                              <div className="mt-1 text-xs text-muted-foreground pl-6">
                                {cmd.exitCode === 0 ? 'Success' : `Exit code: ${cmd.exitCode}`}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  
                  <div className="p-2 border-t border-border bg-muted/30">
                    <button
                      onClick={() => {
                        terminal.clearCommands()
                        ui.closeTerminalDropdown()
                      }}
                      className="w-full px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
                      disabled={terminal.commands.length === 0}
                    >
                      Clear History
                    </button>
                  </div>
                </div>
              )}
            </div>
            {/* Python Server Status */}
            <button
              onClick={(e) => {
                if (e.shiftKey && pythonServer.isRunning) {
                  e.preventDefault()
                  pythonServer.restartServer()
                } else {
                  pythonServer.startServer()
                }
              }}
              disabled={pythonServer.isStarting}
              className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 bg-background text-white hover:bg-muted"
              title={
                pythonServer.isStarting
                  ? 'Starting Python server...'
                  : pythonServer.isRunning && !pythonServer.isStale
                    ? `Python server on port ${pythonServer.port} (Shift+Click to restart)`
                    : pythonServer.isRunning && pythonServer.isStale
                      ? `Python server status unknown (last check >10s ago) - click to verify`
                      : 'Python server is offline - click to start'
              }
            >
              {pythonServer.isStarting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>...</span>
                </>
              ) : pythonServer.isRunning && !pythonServer.isStale ? (
                <>
                  <Server className="w-4 h-4" />
                  <span>:{pythonServer.port}</span>
                </>
              ) : pythonServer.isRunning && pythonServer.isStale ? (
                <>
                  <Server className="w-4 h-4 text-yellow-400" />
                  <span className="text-yellow-400">:{pythonServer.port}?</span>
                </>
              ) : (
                <>
                  <Server className="w-4 h-4" />
                  <span>Off</span>
                </>
              )}
            </button>
            {/* DEBUG: Kokoro Server Status Button */}
            <button
              onClick={(e) => {
                if (e.shiftKey && kokoroServer.isAvailable) {
                  e.preventDefault()
                  kokoroServer.restartServer()
                } else {
                  kokoroServer.startServer()
                }
              }}
              disabled={kokoroServer.isStarting || kokoroServer.isPolling}
              className={cn(
                "flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50",
                kokoroServer.isAvailable
                  ? "bg-black text-white hover:bg-gray-800"
                  : "bg-muted/50 text-muted-foreground hover:bg-muted/80"
              )}
              title={
                kokoroServer.isStarting
                  ? 'Starting Kokoro server...'
                  : kokoroServer.isPolling
                    ? 'Waiting for Kokoro server to come online...'
                    : kokoroServer.isAvailable
                      ? `Kokoro server on port ${kokoroServer.port} (Shift+Click to restart)`
                      : 'Kokoro server is offline - click to start'
              }
            >
              {kokoroServer.isStarting || kokoroServer.isPolling ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>...</span>
                </>
              ) : kokoroServer.isAvailable ? (
                <>
                  <Volume2 className="w-4 h-4" />
                  <span>:{kokoroServer.port}</span>
                </>
              ) : (
                <>
                  <Volume2 className="w-4 h-4" />
                  <span>None</span>
                </>
              )}
            </button>
            <button
              onClick={chat.showDocumentation}
              className="p-2 rounded-lg hover:bg-muted transition-colors"
              title="Show Documentation"
            >
              <BookOpen className="w-5 h-5 text-muted-foreground" />
            </button>
            <button
              onClick={ui.openSettings}
              className="p-2 rounded-lg hover:bg-muted transition-colors"
              title="Settings"
            >
              <Settings className="w-5 h-5 text-muted-foreground" />
            </button>
          </div>
        </header>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {!chat.currentChat ? (
          <Documentation />
        ) : !chat.messages || chat.messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <Bot className="w-12 h-12 mb-4 opacity-50" />
            <p className="text-lg font-medium">No messages yet</p>
            <p className="text-sm">Start a conversation by typing below</p>
          </div>
        ) : (
          chat.messages
            .filter((message: BranchedMessage) => {
              // Filter out empty assistant messages unless they have agent execution
              if (message.role === 'assistant' && !message.content.trim() && !message.agentExecution) {
                return false
              }
              return true
            })
            .map((message: BranchedMessage, index: number) => (
            <div
              key={index}
              className={cn(
                "flex gap-3",
                message.role === 'user' ? "justify-end" : "justify-start"
              )}
            >
              {message.role === 'assistant' && (
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                  <Bot className="w-5 h-5 text-primary-foreground" />
                </div>
              )}
              
              
              <div
                className={cn(
                  "max-w-[80%] rounded-lg px-4 py-3 flex items-center gap-2",
                  message.role === 'user'
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                )}
              >
                                <div className="flex-1 min-w-0">
                  {/* Inline editing UI */}
                  {branching.editingMessageId === message.messageId ? (
                    <div className="w-full space-y-2">
                      <textarea
                        value={branching.editContent}
                        onChange={(e) => branching.setEditContent(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault()
                            saveEdit(index)
                          } else if (e.key === 'Escape') {
                            branching.cancelEdit()
                          }
                        }}
                        className="w-full bg-white/20 text-primary-foreground rounded px-2 py-1 text-sm resize-none focus:outline-none focus:ring-1 focus:ring-white/50"
                        rows={2}
                        autoFocus
                      />
                      <div className="flex gap-2 justify-end">
                        <button
                          onClick={() => saveEdit(index)}
                          className="px-2 py-1 text-xs bg-white/20 rounded hover:bg-white/30 transition-colors"
                        >
                          Send
                        </button>
                        <button
                          onClick={branching.cancelEdit}
                          className="px-2 py-1 text-xs bg-white/10 rounded hover:bg-white/20 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="text-sm space-y-2">
                        {message.role === 'assistant' && !message.content.trim() ? (
                          null
                        ) : (
                          <MessageContent content={message.content} />
                        )}
                      </div>
                      
                      {/* Agent Execution Tracker */}
                      {message.agentExecution && (
                        <AgentTracker
                          execution={message.agentExecution}
                          onToggleExpand={() => {
                            const newMessages = [...chat.messages]
                            if (newMessages[index].agentExecution) {
                              newMessages[index].agentExecution!.isExpanded = !newMessages[index].agentExecution!.isExpanded
                              chat.setMessages(newMessages)
                            }
                          }}
                          onToggleAgent={(agentName) => {
                            const newMessages = [...chat.messages]
                            const exec = newMessages[index].agentExecution
                            if (exec) {
                              exec.agents = exec.agents.map(agent =>
                                agent.name === agentName
                                  ? { ...agent, isExpanded: !agent.isExpanded }
                                  : agent
                              )
                              chat.setMessages(newMessages)
                            }
                          }}
                        />
                      )}
                      
                      {message.role === 'assistant' && (
                        <div className="flex items-center gap-2 mt-2">
                          {/* Branch switcher for assistant message itself (inference side branching) */}
                          {message.branches && message.branches.length > 0 && (
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => {
                                  const currentIdx = message.currentBranchIndex ?? -1
                                  const savedBranches = message.branches?.filter(b => !b.messageId.startsWith('current-')) || []
                                  const savedCount = savedBranches.length
                                  let newIndex: number
                                  if (currentIdx === -1) {
                                    newIndex = savedCount - 1
                                  } else if (currentIdx === 0) {
                                    newIndex = -1
                                  } else {
                                    newIndex = currentIdx - 1
                                  }
                                  switchBranch(index, newIndex)
                                }}
                                className="p-1 rounded hover:bg-muted-foreground/20 transition-colors"
                                title="Previous AI response"
                              >
                                <ChevronLeft className="w-3 h-3 text-muted-foreground" />
                              </button>
                              <span className="text-xs text-muted-foreground opacity-70">
                                {(() => {
                                  const currentIdx = message.currentBranchIndex ?? -1
                                  const savedBranches = message.branches?.filter(b => !b.messageId.startsWith('current-')) || []
                                  const totalVersions = savedBranches.length + 1
                                  const displayPosition = currentIdx === -1 ? totalVersions : currentIdx + 1
                                  return `${displayPosition} / ${totalVersions}`
                                })()}
                              </span>
                              <button
                                onClick={() => {
                                  const currentIdx = message.currentBranchIndex ?? -1
                                  const savedBranches = message.branches?.filter(b => !b.messageId.startsWith('current-')) || []
                                  const savedCount = savedBranches.length
                                  let newIndex: number
                                  if (currentIdx === -1) {
                                    newIndex = 0
                                  } else if (currentIdx >= savedCount - 1) {
                                    newIndex = -1
                                  } else {
                                    newIndex = currentIdx + 1
                                  }
                                  switchBranch(index, newIndex)
                                }}
                                className="p-1 rounded hover:bg-muted-foreground/20 transition-colors"
                                title="Next AI response"
                              >
                                <ChevronRight className="w-3 h-3 text-muted-foreground" />
                              </button>
                            </div>
                          )}
                          <button
                            onClick={() => tts.speakMessage(message.content, index, chat.config.ttsVoice)}
                            className="p-1 rounded hover:bg-muted-foreground/20 transition-colors"
                            title={tts.isSpeaking ? "Stop speaking" : tts.generatingMessageIndex === index ? "Generating audio..." : "Read aloud"}
                            disabled={tts.generatingMessageIndex !== null}
                          >
                            {tts.generatingMessageIndex === index ? (
                              <Loader2 className="w-4 h-4 text-muted-foreground animate-spin" />
                            ) : tts.isSpeaking ? (
                              <VolumeX className="w-4 h-4 text-muted-foreground" />
                            ) : (
                              <Volume2 className="w-4 h-4 text-muted-foreground" />
                            )}
                          </button>
                          <button
                            onClick={() => copyToClipboard(message.messageId, message.content)}
                            className="p-1 rounded hover:bg-muted-foreground/20 transition-colors"
                            title={branching.copiedMessageId === message.messageId ? "Copied!" : "Copy to clipboard"}
                          >
                            {branching.copiedMessageId === message.messageId ? (
                              <Check className="w-4 h-4 text-white" />
                            ) : (
                              <Clipboard className="w-4 h-4 text-muted-foreground" />
                            )}
                          </button>
                          <button
                            onClick={() => resendMessage(chat.messages[index - 1]?.content || '', index)}
                            className="p-1 rounded hover:bg-muted-foreground/20 transition-colors"
                            title="Regenerate this message"
                          >
                            <RotateCcw className="w-4 h-4 text-muted-foreground" />
                          </button>
                        </div>
                      )}
                      
                      {/* Edit button below user message content */}
                      {message.role === 'user' && branching.editingMessageId !== message.messageId && (
                        <div className="flex items-center gap-2 mt-2 justify-end">
                          {/* Branch switcher with arrows around version counter */}
                          {message.branches && message.branches.length > 0 && (
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => {
                                  const currentIdx = message.currentBranchIndex ?? -1
                                  const savedBranches = message.branches?.filter(b => !b.messageId.startsWith('current-')) || []
                                  const savedCount = savedBranches.length
                                  // Cycle: current (-1) → last saved branch → ... → first saved branch → current (-1)
                                  let newIndex: number
                                  if (currentIdx === -1) {
                                    newIndex = savedCount - 1
                                  } else if (currentIdx === 0) {
                                    newIndex = -1
                                  } else {
                                    newIndex = currentIdx - 1
                                  }
                                  switchBranch(index, newIndex)
                                }}
                                className="p-1 rounded hover:bg-white/20 transition-colors"
                                title="Previous version"
                              >
                                <ChevronLeft className="w-3 h-3" />
                              </button>
                              <span className="text-xs opacity-70">
                                {(() => {
                                  const currentIdx = message.currentBranchIndex ?? -1
                                  const savedBranches = message.branches?.filter(b => !b.messageId.startsWith('current-')) || []
                                  const totalVersions = savedBranches.length + 1
                                  const displayPosition = currentIdx === -1 ? totalVersions : currentIdx + 1
                                  return `${displayPosition} / ${totalVersions}`
                                })()}
                              </span>
                              <button
                                onClick={() => {
                                  const currentIdx = message.currentBranchIndex ?? -1
                                  const savedBranches = message.branches?.filter(b => !b.messageId.startsWith('current-')) || []
                                  const savedCount = savedBranches.length
                                  // Cycle: current (-1) → first saved branch → ... → last saved branch → current (-1)
                                  let newIndex: number
                                  if (currentIdx === -1) {
                                    newIndex = 0
                                  } else if (currentIdx >= savedCount - 1) {
                                    newIndex = -1
                                  } else {
                                    newIndex = currentIdx + 1
                                  }
                                  switchBranch(index, newIndex)
                                }}
                                className="p-1 rounded hover:bg-white/20 transition-colors"
                                title="Next version"
                              >
                                <ChevronRight className="w-3 h-3" />
                              </button>
                            </div>
                          )}
                          <button
                            onClick={() => {
                              branching.startEdit(message.messageId, message.content)
                            }}
                            className="p-1 rounded hover:bg-white/20 transition-colors"
                            title="Edit this message"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => copyToClipboard(message.messageId, message.content)}
                            className="p-1 rounded hover:bg-white/20 transition-colors"
                            title={branching.copiedMessageId === message.messageId ? "Copied!" : "Copy to clipboard"}
                          >
                            {branching.copiedMessageId === message.messageId ? (
                              <Check className="w-4 h-4 text-black" />
                            ) : (
                              <Clipboard className="w-4 h-4" />
                            )}
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
              
              {message.role === 'user' && (
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-secondary flex items-center justify-center">
                  <User className="w-5 h-5 text-secondary-foreground" />
                </div>
              )}
            </div>
          )))}
        <div ref={chat.messagesEndRef} />
      </div>

      {/* Input - only show when chat is active */}
      {chat.currentChat && (
        <div className="p-4 border-t border-border bg-card">
          <div className="flex items-end gap-2 max-w-4xl mx-auto">
            <div className="flex-1 relative">
              <textarea
                id="message-input"
                name="message"
                ref={chat.textareaRef}
                value={chat.input}
                onChange={(e) => chat.setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSubmit()
                  }
                }}
                placeholder="Type a message..."
                className="w-full min-h-[44px] max-h-[200px] rounded-lg border border-input bg-background px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring appearance-none"
                rows={1}
                disabled={chat.isLoading}
              />
            </div>
            <button
              onClick={chat.isLoading ? chat.stopGeneration : handleSubmit}
              disabled={!chat.isLoading && !chat.input.trim()}
              className={cn(
                "flex-shrink-0 p-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
                chat.isLoading
                  ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              )}
              title={chat.isLoading ? "Stop inference" : "Send message"}
            >
              {chat.isLoading ? <Square className="w-5 h-5" /> : <Send className="w-5 h-5" />}
            </button>
            {/* Split clipboard - left for current branch, right for all branches */}
            <div className="flex-shrink-0 flex rounded-lg overflow-hidden bg-background group relative">
              {ui.chatCopied ? (
                /* Unified checkmark spanning both buttons */
                <div className="flex items-center justify-center w-[5.5rem] h-11 bg-background">
                  <Check className="w-5 h-5 text-green-500" />
                </div>
              ) : (
                <>
                  {/* Left half - Copy current branch (what AI sees) */}
                  <button
                    onClick={() => {
                      // Copy exactly what is sent to the AI (same as getCurrentBranchPath)
                      const branchPath = getCurrentBranchPath(chat.messages)
                      const chatText = branchPath.map(m => {
                        const role = m.role === 'user' ? 'User' : 'Rogius'
                        return `${role}: ${m.content}`
                      }).join('\n\n')
                      navigator.clipboard.writeText(chatText)
                      ui.triggerChatCopied()
                    }}
                    disabled={chat.messages.length === 0}
                    className="p-3 bg-background text-muted-foreground hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Copy current branch"
                  >
                    <Clipboard className="w-5 h-5" />
                  </button>
                  {/* Right half - Copy all branches */}
                  <button
                    onClick={() => {
                      // Include all branches in the export
                      let allText = ''

                      for (let i = 0; i < chat.messages.length; i++) {
                        const msg = chat.messages[i]
                        const role = msg.role === 'user' ? 'User' : 'Rogius'

                        // Add current message
                        allText += `${role}: ${msg.content}\n\n`

                        // Add all branches for user messages (skip current version slot)
                        if (msg.role === 'user' && msg.branches && msg.branches.length > 0) {
                          msg.branches.forEach((branch, idx) => {
                            // Skip the "current version" slot - it's already in the main message stream
                            if (branch.messageId.startsWith('current-')) return
                            allText += `[Branch ${idx + 1}] ${role}: ${branch.content}\n\n`
                            // Add subtree messages for this branch
                            if (branch.subtree) {
                              branch.subtree.forEach(subMsg => {
                                const subRole = subMsg.role === 'user' ? 'User' : 'Rogius'
                                allText += `  ${subRole}: ${subMsg.content}\n\n`
                              })
                            }
                          })
                        }
                      }

                      navigator.clipboard.writeText(allText.trim())
                      ui.triggerChatCopied()
                    }}
                    disabled={chat.messages.length === 0}
                    className="p-3 bg-background text-muted-foreground hover:bg-muted transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Copy all branches"
                  >
                    <span className="text-xs font-bold px-1 text-muted-foreground">ALL</span>
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

        {/* Settings Modal */}
        {ui.showSettings && (
          <SettingsModal
            config={chat.config}
            systemInfo={terminal.systemInfo}
            onSave={(newConfig) => {
              chat.setConfig(newConfig)
              ui.closeSettings()
            }}
            onClose={ui.closeSettings}
          />
        )}

      </div>
    </div>
  )
}
