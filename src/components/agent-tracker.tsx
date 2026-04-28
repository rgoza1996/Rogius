'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { AgentExecutionState, AgentStatus, AgentPhase } from '@/lib/chat-storage'
import {
  ChevronDown,
  ChevronRight,
  Search,
  ClipboardList,
  Terminal,
  CheckCircle,
  AlertCircle,
  Loader2,
  Clock,
  Bot,
  FileText,
} from 'lucide-react'

interface AgentTrackerProps {
  execution: AgentExecutionState
  onToggleExpand: () => void
  onToggleAgent?: (agentName: string) => void
}

const agentIcons: Record<string, React.ReactNode> = {
  'Investigator': <Search className="w-4 h-4" />,
  'Planner': <ClipboardList className="w-4 h-4" />,
  'Executor': <Terminal className="w-4 h-4" />,
  'Verifier': <CheckCircle className="w-4 h-4" />,
  'Reporter': <FileText className="w-4 h-4" />,
  'Rogius': <Bot className="w-4 h-4" />,
}

const agentDescriptions: Record<string, string> = {
  'Investigator': 'Probing environment',
  'Planner': 'Creating execution plan',
  'Executor': 'Running commands',
  'Verifier': 'Verifying results',
  'Reporter': 'Generating report',
  'Rogius': 'Orchestrating workflow',
}

const statusColors = {
  pending: 'text-muted-foreground',
  running: 'text-blue-500',
  completed: 'text-green-500',
  error: 'text-red-500',
}

const statusIcons = {
  pending: <Clock className="w-4 h-4" />,
  running: <Loader2 className="w-4 h-4 animate-spin" />,
  completed: <CheckCircle className="w-4 h-4" />,
  error: <AlertCircle className="w-4 h-4" />,
}

function getPhaseFromEventType(eventType: string): AgentPhase {
  switch (eventType) {
    case 'phase':
      return 'investigation'
    case 'step_start':
    case 'step_complete':
    case 'step_error':
      return 'execution'
    case 'complete':
      return 'complete'
    case 'error':
      return 'error'
    default:
      return 'execution'
  }
}

export function AgentTracker({ execution, onToggleExpand, onToggleAgent }: AgentTrackerProps) {
  const progress = execution.totalSteps > 0
    ? Math.round((execution.completedSteps / execution.totalSteps) * 100)
    : 0

  // Find current running agent
  const currentAgent = execution.agents.find(a => a.status === 'running')
  const currentAgentName = currentAgent?.name || execution.agents[execution.currentAgentIndex]?.name

  const handleToggleAgent = (agentName: string) => {
    onToggleAgent?.(agentName)
  }

  return (
    <div className="mt-3 border rounded-lg bg-muted/50 overflow-hidden">
      {/* Header - Clickable to expand */}
      <button
        onClick={onToggleExpand}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-muted/80 transition-colors text-left"
      >
        {execution.isExpanded ? (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="w-4 h-4 text-muted-foreground" />
        )}
        
        <Bot className="w-4 h-4 text-primary" />
        
        <span className="text-sm font-medium">
          Multi-Agent Workflow
        </span>
        
        {currentAgentName && (
          <span className="text-xs text-muted-foreground">
            • {currentAgentName} active
          </span>
        )}
        
        <div className="ml-auto flex items-center gap-2">
          {/* Progress bar */}
          <div className="w-20 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground w-10 text-right">
            {progress}%
          </span>
        </div>
      </button>

      {/* Expanded Content */}
      {execution.isExpanded && (
        <div className="px-3 pb-3 border-t">
          {/* Agent List */}
          <div className="py-2 space-y-1">
            {execution.agents.map((agent, index) => (
              <AgentRow
                key={agent.name}
                agent={agent}
                isActive={index === execution.currentAgentIndex}
                isCurrent={agent.status === 'running'}
                onToggle={() => handleToggleAgent(agent.name)}
              />
            ))}
          </div>

          {/* Execution Log */}
          {execution.log.length > 0 && (
            <div className="mt-2 pt-2 border-t">
              <div className="text-xs font-medium text-muted-foreground mb-1">
                Execution Log
              </div>
              <div className="text-xs font-mono bg-black/5 rounded p-2 max-h-64 overflow-y-auto space-y-0.5">
                {execution.log.map((line, i) => (
                  <div key={i} className="text-muted-foreground">
                    {line}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function AgentRow({
  agent,
  isActive,
  isCurrent,
  onToggle,
}: {
  agent: AgentStatus
  isActive: boolean
  isCurrent: boolean
  onToggle: () => void
}) {
  const hasContent = Boolean(agent.systemPrompt || agent.userPrompt || agent.inference)
  const isStreamingInference = isCurrent && agent.inference === undefined
  const hasDetails = hasContent || isStreamingInference

  return (
    <div className="space-y-1">
      <button
        onClick={onToggle}
        disabled={!hasDetails}
        className={cn(
          "w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm text-left transition-colors bg-background",
          isCurrent && "bg-primary/10 ring-1 ring-primary/30",
          !isActive && !isCurrent && "opacity-60",
          hasDetails && "hover:bg-muted/80 cursor-pointer",
          !hasDetails && "cursor-default"
        )}
      >
        <span className="text-muted-foreground">
          {agentIcons[agent.name] || <Bot className="w-4 h-4" />}
        </span>
        
        <span className={cn(
          "font-medium flex-1",
          isCurrent ? "text-foreground" : "text-muted-foreground"
        )}>
          {agent.name}
        </span>

        {hasDetails && (
          <span className="text-muted-foreground">
            {agent.isExpanded ? (
              <ChevronDown className="w-3 h-3" />
            ) : (
              <ChevronRight className="w-3 h-3" />
            )}
          </span>
        )}
        
        <span className="text-xs text-muted-foreground">
          {agentDescriptions[agent.name] || agent.phase}
        </span>
      </button>
      
      {/* Expanded Details */}
      {agent.isExpanded && hasDetails && (
        <div className="ml-6 space-y-2 text-xs">
          {agent.systemPrompt && (
            <div className="bg-muted/50 rounded p-2">
              <div className="font-medium text-muted-foreground mb-1">System Prompt</div>
              <pre className="font-mono text-muted-foreground whitespace-pre-wrap break-words max-h-32 overflow-y-auto">
                {agent.systemPrompt}
              </pre>
            </div>
          )}
          
          {agent.userPrompt && (
            <div className="bg-muted/50 rounded p-2">
              <div className="font-medium text-muted-foreground mb-1">
                {agent.fromAgent ? `From ${agent.fromAgent}` : 'User Prompt'}
              </div>
              <pre className="font-mono text-muted-foreground whitespace-pre-wrap break-words max-h-32 overflow-y-auto">
                {agent.userPrompt}
              </pre>
            </div>
          )}
          
          {(agent.inference || isStreamingInference) && (
            <div className="bg-muted/50 rounded p-2">
              <div className="font-medium text-muted-foreground mb-1 flex items-center gap-2">
                Inference (LLM Response)
              </div>
              <pre 
                className="font-mono text-foreground whitespace-pre-wrap break-words min-h-[60px] max-h-96 overflow-y-auto resize-y"
                style={{ resize: 'vertical' }}
              >
                {agent.inference || '(waiting for response...)'}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
