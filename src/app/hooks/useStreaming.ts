'use client'

import { useCallback, useRef } from 'react'
import type { APIConfig, ChatMessage, ToolCall } from '@/lib/api-client'
import { streamChatCompletion } from '@/lib/api-client'
import {
  BranchedMessage,
  createBranchedMessage,
  AgentExecutionState,
  AgentStatus,
  saveChat,
  getChat,
  ChatSession,
} from '@/lib/chat-storage'
import type { UseChatReturn } from './useChat'
import type { TerminalState, TerminalCommand } from '@/tools/terminal'
import { pythonBridge } from '@/lib/python-bridge'

export interface StreamingState {
  isStreaming: boolean
  assistantContent: string
  assistantMessage: BranchedMessage | null
}

export interface UseStreamingReturn {
  streamResponse: (
    apiMessages: ChatMessage[],
    currentMessages: BranchedMessage[],
    onToolCall?: (toolCall: ToolCall) => Promise<string | null>
  ) => Promise<{
    content: string
    assistantMessage: BranchedMessage
    toolResults: string[]
  } | null>
}

export interface TerminalActions {
  executeCommand: (command: string, confirmOverride?: boolean) => Promise<TerminalCommand>
}

export function useStreaming(
  chat: Pick<UseChatReturn, 'config' | 'setMessages' | 'setIsLoading' | 'abortControllerRef' | 'currentChat' | 'currentChatRef'>,
  terminal: TerminalActions
): UseStreamingReturn {
  const pendingToolCallsMapRef = useRef<Map<number, ToolCall>>(new Map())

  const streamResponse = useCallback(async (
    apiMessages: ChatMessage[],
    currentMessages: BranchedMessage[],
    onToolCall?: (toolCall: ToolCall) => Promise<string | null>
  ): Promise<{
    content: string
    assistantMessage: BranchedMessage
    toolResults: string[]
  } | null> => {
    // Capture target chat at start - output always goes here even if user switches
    const targetChat = chat.currentChat
    const targetChatId = targetChat?.id
    const setMessages = chat.setMessages
    
    if (!targetChatId) {
      console.error('[streamResponse] No current chat, cannot stream')
      return null
    }
    
    chat.setIsLoading(true)
    chat.abortControllerRef.current = new AbortController()
    pendingToolCallsMapRef.current.clear()

    // Helper to save messages to the target chat (regardless of which chat is currently viewed)
    const saveMessagesToTargetChat = async (messages: BranchedMessage[]) => {
      try {
        const chat = await getChat(targetChatId)
        if (chat) {
          await saveChat({ ...chat, messages, updatedAt: Date.now() })
        }
      } catch (err) {
        console.error('[saveMessagesToTargetChat] Error:', err)
      }
    }
    
    // Helper to update UI only if still viewing the target chat
    // Use currentChatRef for live access (not captured value)
    const updateUI = (messages: BranchedMessage[]) => {
      if (chat.currentChatRef.current?.id === targetChatId) {
        setMessages(messages)
      }
    }

    let assistantContent = ''
    // Check if last message is an empty assistant message (regeneration case)
    const lastMessage = currentMessages[currentMessages.length - 1]
    const isRegenerating = lastMessage?.role === 'assistant' && !lastMessage.content.trim()
    const assistantMessage = isRegenerating 
      ? { ...lastMessage, content: '' }  // Reuse existing message for regeneration
      : createBranchedMessage('assistant', '')
    // For regeneration, we need to use messages without the last empty one
    const baseMessages = isRegenerating ? currentMessages.slice(0, -1) : currentMessages

    try {
      for await (const chunk of streamChatCompletion(
        apiMessages,
        chat.config,
        true,
        chat.abortControllerRef.current.signal
      )) {
        if (chunk.content) {
          const contentStr = String(chunk.content)
          // Skip if content looks like a tool call
          if (contentStr.includes('[object Object]') || contentStr.trim().startsWith('{')) {
            console.log('Skipping object-like content:', contentStr.substring(0, 100))
          } else {
            assistantContent += contentStr
            if (chat.abortControllerRef.current?.signal.aborted) return null
            const newMessages = [...baseMessages, { ...assistantMessage, content: assistantContent }]
            saveMessagesToTargetChat(newMessages)
            updateUI(newMessages)
          }
        }

        if (chunk.toolCalls) {
          // Accumulate tool calls properly (they come in chunks)
          for (const tc of chunk.toolCalls) {
            const idx = tc.index ?? 0
            const existing = pendingToolCallsMapRef.current.get(idx)
            if (existing) {
              existing.function.name = tc.function?.name || existing.function?.name
              existing.function.arguments += tc.function?.arguments || ''
              existing.id = tc.id || existing.id
            } else {
              pendingToolCallsMapRef.current.set(idx, {
                id: tc.id,
                type: tc.type,
                function: {
                  name: tc.function?.name,
                  arguments: tc.function?.arguments || ''
                }
              })
            }
          }
        }
      }

      // Handle tool calls
      const toolResults: string[] = []
      const pendingToolCalls = Array.from(pendingToolCallsMapRef.current.values())
      
      if (pendingToolCalls.length > 0) {
        console.log('Executing tool calls:', pendingToolCalls)
        for (const toolCall of pendingToolCalls) {
          if (onToolCall) {
            const result = await onToolCall(toolCall)
            if (result) {
              toolResults.push(result)
              assistantContent += result
            }
          } else if (toolCall.function.name === 'open_terminal') {
            // Actually execute a PowerShell command to show terminal info
            const result = await terminal.executeCommand('Get-Location; Write-Host "PowerShell Terminal Active" -ForegroundColor Green')
            const output = result.stdout || result.stderr || '(no output)'
            const formattedResult = `
\`\`\`terminal
$ Get-Location; Write-Host "PowerShell Terminal Active" -ForegroundColor Green
${output}
\`\`\``
            toolResults.push(formattedResult)
            assistantContent += formattedResult
          } else if (toolCall.function.name === 'execute_command') {
            const args = JSON.parse(toolCall.function.arguments)
            console.log('Executing command:', args.command)
            const result = await terminal.executeCommand(args.command)
            const output = result.stdout || result.stderr || '(no output)'
            const formattedResult = `\n\`\`\`terminal\n$ ${args.command}\n${output}\n\`\`\``
            toolResults.push(formattedResult)
            assistantContent += formattedResult
          } else if (toolCall.function.name === 'start_multistep_task') {
            const args = JSON.parse(toolCall.function.arguments)
            console.log('Starting streaming agentic multi-step task:', args.goal)
            try {
              // Use streaming agentic execution for real-time updates
              let logLines: string[] = []
              let finalStatus = 'running'
              let completed = 0
              // Handle both old format (with steps array) and new multi-agent format (no steps)
              const steps = Array.isArray(args.steps) ? args.steps : []
              let total = steps.length || 0
              
              // Initialize agent execution state for tracking
              const initialAgentExecution: AgentExecutionState = {
                goal: args.goal,
                agents: [
                  { name: 'Investigator', phase: 'investigation', status: 'pending', timestamp: Date.now() },
                  { name: 'Planner', phase: 'planning', status: 'pending', timestamp: Date.now() },
                  { name: 'Executor', phase: 'execution', status: 'pending', timestamp: Date.now() },
                  { name: 'Verifier', phase: 'verification', status: 'pending', timestamp: Date.now() },
                  { name: 'Reporter', phase: 'reporting', status: 'pending', timestamp: Date.now() },
                ],
                currentAgentIndex: 0,
                totalSteps: 0,
                completedSteps: 0,
                isExpanded: true, // Auto-expand when starting
                log: ['Starting multi-agent workflow...'],
              }
              
              // Attach agent execution state to the assistant message
              if (chat.abortControllerRef.current?.signal.aborted) return null
              const agentInitMessages = [...baseMessages, { ...assistantMessage, agentExecution: initialAgentExecution }]
              saveMessagesToTargetChat(agentInitMessages)
              updateUI(agentInitMessages)

              const stream = pythonBridge.multistep.executeAgenticStream({
                goal: args.goal,
                steps: steps.map((s: {description: string, command: string}) => ({
                  description: s.description,
                  command: s.command
                })),
                max_iterations: 50
              })

              // Initial message
              const initialMsg = `\n\`\`\`terminal\n[Agentic Plan] ${args.goal}\nProgress: 0/${total} (0%)\nStatus: starting...\n\nStarting execution...\n\`\`\``
              toolResults.push(initialMsg)
              assistantContent += initialMsg
              // Preserve agentExecution in all message updates
              assistantMessage.agentExecution = initialAgentExecution
              if (chat.abortControllerRef.current?.signal.aborted) return null
              const agentStartMessages = [...baseMessages, { ...assistantMessage, content: assistantContent, agentExecution: assistantMessage.agentExecution }]
              saveMessagesToTargetChat(agentStartMessages)
              updateUI(agentStartMessages)

              for await (const event of stream) {
                // Get latest execution state from current messages to preserve isExpanded state
                const latestMessages = [...currentMessages]
                const lastMsg = latestMessages[latestMessages.length - 1]
                const exec: AgentExecutionState | undefined = lastMsg?.role === 'assistant' 
                  ? lastMsg.agentExecution 
                  : assistantMessage.agentExecution
                
                // Update agent execution state based on event type
                if (exec) {
                  
                  if (event.type === 'agent_prompt') {
                    // Store prompt for the agent
                    const agentIdx = exec.agents.findIndex((a: AgentStatus) => a.name === event.agent)
                    if (agentIdx !== -1) {
                      assistantMessage.agentExecution = {
                        ...exec,
                        agents: exec.agents.map((a: AgentStatus, idx: number) =>
                          idx === agentIdx
                            ? { ...a, systemPrompt: event.system_prompt, userPrompt: event.user_prompt, fromAgent: event.from_agent }
                            : a
                        )
                      }
                    }
                  } else if (event.type === 'agent_inference_chunk') {
                    // Append streaming inference chunk for real-time display
                    const agentIdx = exec.agents.findIndex((a: AgentStatus) => a.name === event.agent)
                    if (agentIdx !== -1) {
                      const currentInference: string = exec.agents[agentIdx].inference || ''
                      assistantMessage.agentExecution = {
                        ...exec,
                        agents: exec.agents.map((a: AgentStatus, idx: number) =>
                          idx === agentIdx
                            ? { ...a, inference: currentInference + event.chunk }
                            : a
                        )
                      }
                    }
                  } else if (event.type === 'agent_inference') {
                    // Store final parsed inference response for the agent
                    const agentIdx = exec.agents.findIndex((a: AgentStatus) => a.name === event.agent)
                    if (agentIdx !== -1) {
                      assistantMessage.agentExecution = {
                        ...exec,
                        agents: exec.agents.map((a: AgentStatus, idx: number) =>
                          idx === agentIdx
                            ? { ...a, inference: event.response }
                            : a
                        )
                      }
                    }
                  } else if (event.type === 'phase') {
                    // Map phase events to agents
                    const phaseToAgent: Record<string, number> = {
                      'investigation': 0,
                      'planning': 1,
                      'reporting': 4,
                    }
                    const agentIdx = phaseToAgent[event.phase]
                    if (agentIdx !== undefined) {
                      assistantMessage.agentExecution = {
                        ...exec,
                        currentAgentIndex: agentIdx,
                        agents: exec.agents.map((a: AgentStatus, idx: number) => 
                          idx === agentIdx 
                            ? { ...a, status: 'running' as const, phase: event.phase as AgentStatus['phase'], timestamp: Date.now() }
                            : a
                        ),
                        log: [...exec.log, `${exec.agents[agentIdx].name}: ${event.message || event.phase}`]
                      }
                    }
                  } else if (event.type === 'start') {
                    assistantMessage.agentExecution = {
                      ...exec,
                      totalSteps: event.total_steps,
                      currentAgentIndex: 2,
                      agents: exec.agents.map((a: AgentStatus, idx: number) => {
                        if (idx === 0 || idx === 1) return { ...a, status: 'completed' as const }
                        if (idx === 2) return { ...a, status: 'running' as const }
                        return a
                      }),
                      log: [...exec.log, `Plan created with ${event.total_steps} steps`]
                    }
                  } else if (event.type === 'step_start') {
                    assistantMessage.agentExecution = {
                      ...exec,
                      currentAgentIndex: 2,
                      agents: exec.agents.map((a: AgentStatus, idx: number) => {
                        if (idx === 2) return { ...a, status: 'running' as const, description: event.description }
                        if (idx === 3) return { ...a, status: 'completed' as const }
                        return a
                      }),
                      log: [...exec.log, `Step ${event.step}: ${event.description}`]
                    }
                  } else if (event.type === 'step_complete') {
                    assistantMessage.agentExecution = {
                      ...exec,
                      completedSteps: exec.completedSteps + 1,
                      currentAgentIndex: 3,
                      agents: exec.agents.map((a: AgentStatus, idx: number) => {
                        if (idx === 2) return { ...a, status: 'completed' as const }
                        if (idx === 3) return { ...a, status: 'running' as const, description: 'Verifying step result' }
                        return a
                      })
                    }
                  } else if (event.type === 'step_error') {
                    assistantMessage.agentExecution = {
                      ...exec,
                      log: [...exec.log, `Error: ${event.error}`]
                    }
                  } else if (event.type === 'complete') {
                    assistantMessage.agentExecution = {
                      ...exec,
                      completedSteps: event.completed,
                      totalSteps: event.total,
                      agents: exec.agents.map((a: AgentStatus) => ({ ...a, status: 'completed' as const })),
                      log: [...exec.log, `Workflow complete: ${event.completed}/${event.total} steps`]
                    }
                  } else if (event.type === 'error') {
                    assistantMessage.agentExecution = {
                      ...exec,
                      agents: exec.agents.map((a: AgentStatus, idx: number) => 
                        idx === exec.currentAgentIndex ? { ...a, status: 'error' as const } : a
                      ),
                      log: [...exec.log, `Error: ${event.message}`]
                    }
                  }
                  
                  // Trigger UI update with new object references (preserve current content)
                  if (chat.abortControllerRef.current?.signal.aborted) return null
                  const eventMessages = [...baseMessages, { ...assistantMessage, content: assistantContent || '' }]
                  saveMessagesToTargetChat(eventMessages)
                  updateUI(eventMessages)
                }
                
                if (event.type === 'start') {
                  logLines.push(`Starting ${event.total_steps} steps...`)
                } else if (event.type === 'step_start') {
                  logLines.push(`\n[${event.step}] ▶ ${event.description}`)
                } else if (event.type === 'step_complete') {
                  logLines.push(`[${event.step}] ✓ Done`)
                  // Show actual output if meaningful
                  if (event.output && event.output !== '(no output)') {
                    const outputLines = event.output.split('\n').slice(0, 10).join('\n') // First 10 lines
                    logLines.push(`    Output:\n${outputLines.split('\n').map((line: string) => '    ' + line).join('\n')}`)
                  }
                  completed++
                } else if (event.type === 'step_error') {
                  logLines.push(`[${event.step}] ✗ ${event.error}`)
                  if (event.output) {
                    logLines.push(`    Output: ${event.output.slice(0, 200)}`)
                  }
                } else if (event.type === 'step_warn') {
                  logLines.push(`[${event.step}] ⚠ ${event.message}`)
                  if (event.output) {
                    logLines.push(`    Output: ${event.output.slice(0, 200)}`)
                  }
                  completed++  // Count warned as completed
                } else if (event.type === 'retry') {
                  const hintStr = event.hint && event.hint !== 'none' ? ` (${event.hint})` : ''
                  logLines.push(`[${event.step}] 🔄 Retry attempt ${event.attempt}${hintStr}`)
                } else if (event.type === 'decision') {
                  logLines.push(`🤖 AI: ${event.action}${event.reasoning ? ' - ' + event.reasoning : ''}`)
                } else if (event.type === 'complete') {
                  finalStatus = event.status
                  completed = event.completed
                  total = event.total
                  // Mark Executor and Verifier as completed, Reporter as running
                  const completeExec: AgentExecutionState | undefined = assistantMessage.agentExecution
                  if (completeExec) {
                    assistantMessage.agentExecution = {
                      ...completeExec,
                      currentAgentIndex: 4,
                      agents: completeExec.agents.map((a: AgentStatus, idx: number) => {
                        if (idx === 2 || idx === 3) return { ...a, status: 'completed' as const }
                        if (idx === 4) return { ...a, status: 'running' as const }
                        return a
                      })
                    }
                  }
                } else if (event.type === 'error') {
                  logLines.push(`Error: ${event.message}`)
                } else if (event.type === 'report') {
                  // Final user-friendly report from Reporter agent
                  logLines.push('')
                  logLines.push('=== REPORT ===')
                  logLines.push(event.report)
                  // Mark Reporter as completed
                  const reportExec: AgentExecutionState | undefined = assistantMessage.agentExecution
                  if (reportExec) {
                    assistantMessage.agentExecution = {
                      ...reportExec,
                      agents: reportExec.agents.map((a: AgentStatus, idx: number) =>
                        idx === 4 ? { ...a, status: 'completed' as const } : a
                      )
                    }
                  }
                }

                // Update chat in real-time
                const currentLog = logLines.join('\n') // Show full logs
                const progressMsg = `\n\`\`\`terminal\n[Agentic Plan] ${args.goal}\nProgress: ${completed}/${total} (${Math.round((completed/total)*100)}%)\nStatus: ${finalStatus}\n\n${currentLog}\n\`\`\``

                // Replace the last plan message with updated progress
                const lastIdx = toolResults.length - 1
                if (toolResults[lastIdx]?.includes('[Agentic Plan]')) {
                  toolResults[lastIdx] = progressMsg
                } else {
                  toolResults.push(progressMsg)
                }

                // Update assistant content and trigger UI update via React state
                assistantContent = assistantContent.replace(
                  /```terminal\n\[Agentic Plan\][\s\S]*?```$/,
                  progressMsg
                ) || assistantContent + progressMsg
                // Get latest execution state to preserve isExpanded
                const latestMsg = currentMessages[currentMessages.length - 1]
                const currentExec: AgentExecutionState | undefined = latestMsg?.role === 'assistant'
                  ? latestMsg.agentExecution
                  : assistantMessage.agentExecution
                if (chat.abortControllerRef.current?.signal.aborted) return null
                const progressMessages = currentExec
                  ? [...baseMessages, { ...assistantMessage, content: assistantContent, agentExecution: { ...currentExec } }]
                  : [...baseMessages, { ...assistantMessage, content: assistantContent }]
                saveMessagesToTargetChat(progressMessages)
                updateUI(progressMessages)
              }

              // Final message
              const finalMsg = `\n\`\`\`terminal\n[Agentic Plan Complete] ${args.goal}\nExecuted: ${completed}/${total} steps\nStatus: ${finalStatus}\n\nExecution Log:\n${logLines.join('\n')}\n\`\`\``
              const lastIdx = toolResults.length - 1
              if (toolResults[lastIdx]?.includes('[Agentic Plan]')) {
                toolResults[lastIdx] = finalMsg
              } else {
                toolResults.push(finalMsg)
              }
              assistantContent = assistantContent.replace(
                /```terminal\n\[Agentic Plan\][\s\S]*?```$/,
                finalMsg
              ) || assistantContent + finalMsg
              // Preserve agentExecution in final update (use latest state to preserve isExpanded)
              const finalLatestMsg = baseMessages[baseMessages.length - 1]
              const finalExec: AgentExecutionState | undefined = finalLatestMsg?.role === 'assistant'
                ? finalLatestMsg.agentExecution
                : assistantMessage.agentExecution
              if (chat.abortControllerRef.current?.signal.aborted) return null
              const finalMessages = finalExec
                ? [...baseMessages, { ...assistantMessage, content: assistantContent, agentExecution: { ...finalExec } }]
                : [...baseMessages, { ...assistantMessage, content: assistantContent }]
              saveMessagesToTargetChat(finalMessages)
              updateUI(finalMessages)

            } catch (error) {
              const errorMsg = `\n\`\`\`terminal\n[Plan Error] ${error instanceof Error ? error.message : 'Unknown error'}\n\`\`\``
              toolResults.push(errorMsg)
              assistantContent += errorMsg
            }
          } else if (toolCall.function.name === 'execute_next_step') {
            console.log('Executing next step')
            try {
              const result = await pythonBridge.multistep.executeNext()
              const stepMsg = `\n\`\`\`terminal\n[Step ${result.current_step}] Status: ${result.step_status}\n\`\`\``
              toolResults.push(stepMsg)
              assistantContent += stepMsg
            } catch (error) {
              const errorMsg = `\n\`\`\`terminal\n[Step Error] ${error instanceof Error ? error.message : 'Unknown error'}\n\`\`\``
              toolResults.push(errorMsg)
              assistantContent += errorMsg
            }
          } else if (toolCall.function.name === 'modify_step') {
            const args = JSON.parse(toolCall.function.arguments)
            console.log('Modifying step:', args)
            try {
              const result = await pythonBridge.multistep.modify({
                stepIndex: args.stepIndex,
                newCommand: args.newCommand,
                newDescription: args.newDescription
              })
              const modMsg = `\n\`\`\`terminal\n[Step Modified] Step ${result.step_index}\n\`\`\``
              toolResults.push(modMsg)
              assistantContent += modMsg
            } catch (error) {
              const errorMsg = `\n\`\`\`terminal\n[Modify Error] ${error instanceof Error ? error.message : 'Unknown error'}\n\`\`\``
              toolResults.push(errorMsg)
              assistantContent += errorMsg
            }
          } else if (toolCall.function.name === 'skip_step') {
            const args = JSON.parse(toolCall.function.arguments)
            console.log('Skipping step:', args)
            try {
              const result = await pythonBridge.multistep.skip({ stepIndex: args.stepIndex })
              const skipMsg = `\n\`\`\`terminal\n[Step Skipped] Step ${result.step_index}\n\`\`\``
              toolResults.push(skipMsg)
              assistantContent += skipMsg
            } catch (error) {
              const errorMsg = `\n\`\`\`terminal\n[Skip Error] ${error instanceof Error ? error.message : 'Unknown error'}\n\`\`\``
              toolResults.push(errorMsg)
              assistantContent += errorMsg
            }
          } else if (toolCall.function.name === 'add_step') {
            const args = JSON.parse(toolCall.function.arguments)
            console.log('Adding step:', args)
            try {
              const result = await pythonBridge.multistep.add({
                afterStepIndex: args.afterStepIndex,
                description: args.description,
                command: args.command
              })
              const addMsg = `\n\`\`\`terminal\n[Step Added] Position ${result.insert_index}: ${args.description}\n\`\`\``
              toolResults.push(addMsg)
              assistantContent += addMsg
            } catch (error) {
              const errorMsg = `\n\`\`\`terminal\n[Add Error] ${error instanceof Error ? error.message : 'Unknown error'}\n\`\`\``
              toolResults.push(errorMsg)
              assistantContent += errorMsg
            }
          } else if (toolCall.function.name === 'verify_task_completion') {
            console.log('Verifying task completion')
            try {
              const status = await pythonBridge.multistep.status()
              if ('active_plan' in status && status.active_plan === null) {
                const verifyMsg = `\n\`\`\`terminal\n[Verification] No active plan\n\`\`\``
                toolResults.push(verifyMsg)
                assistantContent += verifyMsg
              } else {
                const plan = status as { goal: string; status: string; progress_percentage: number }
                const verifyMsg = `\n\`\`\`terminal\n[Verification] ${plan.goal}\nStatus: ${plan.status} (${plan.progress_percentage}%)\n\`\`\``
                toolResults.push(verifyMsg)
                assistantContent += verifyMsg
              }
            } catch (error) {
              const errorMsg = `\n\`\`\`terminal\n[Verification Error] ${error instanceof Error ? error.message : 'Unknown error'}\n\`\`\``
              toolResults.push(errorMsg)
              assistantContent += errorMsg
            }
          }
        }
        if (chat.abortControllerRef.current?.signal.aborted) return null
        const toolResultMessages = [...baseMessages, { ...assistantMessage, content: assistantContent }]
        saveMessagesToTargetChat(toolResultMessages)
        updateUI(toolResultMessages)
      }

      return {
        content: assistantContent,
        assistantMessage,
        toolResults
      }
    } catch (error) {
      if (error instanceof Error && error.name !== 'AbortError') {
        if (chat.abortControllerRef.current?.signal.aborted) return null
        const errorMessage = createBranchedMessage('assistant', `Error: ${error.message}`)
        const errorMessages = [...baseMessages, errorMessage]
        saveMessagesToTargetChat(errorMessages)
        updateUI(errorMessages)
      }
      return null
    } finally {
      chat.setIsLoading(false)
      chat.abortControllerRef.current = null
    }
  }, [chat, terminal])

  return { streamResponse }
}
