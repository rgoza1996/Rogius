'use client'

import { useState, useEffect } from 'react'
import { X, Eye, EyeOff, RefreshCw, Server, Download, Upload, FileJson, Database, AlertCircle, Check, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { APIConfig, fetchModels } from '@/lib/api-client'
import { SystemInfo } from '@/tools/terminal'
import { getStorageInfo, clearAllChats } from '@/lib/chat-storage'
import { useToast } from '@/components/toast'
import { pythonBridge } from '@/lib/python-bridge'

interface SettingsModalProps {
  config: APIConfig
  systemInfo: SystemInfo | null
  onSave: (config: APIConfig) => void
  onClose: () => void
}

export function SettingsModal({ config, systemInfo, onSave, onClose }: SettingsModalProps) {
  const { showToast } = useToast()
  const [formData, setFormData] = useState<APIConfig>({ ...config })
  const [showChatKey, setShowChatKey] = useState(false)
  const [showTtsKey, setShowTtsKey] = useState(false)
  const [activeTab, setActiveTab] = useState<'chat' | 'tts' | 'system' | 'behavior' | 'data'>('chat')
  const [models, setModels] = useState<string[]>([])
  const [loadingModels, setLoadingModels] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  useEffect(() => {
    if (activeTab === 'chat') {
      loadModels()
    }
  }, [activeTab, formData.chatEndpoint, formData.chatApiKey])

  const loadModels = async () => {
    if (!formData.chatEndpoint) return
    setLoadingModels(true)
    const availableModels = await fetchModels(formData)
    setModels(availableModels)
    setLoadingModels(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    setIsSaving(true)
    try {
      // Python backend is the ONLY place settings are stored
      await pythonBridge.settings.update({
        chat_endpoint: formData.chatEndpoint,
        chat_api_key: formData.chatApiKey,
        chat_model: formData.chatModel,
        chat_context_length: formData.chatContextLength,
        tts_endpoint: formData.ttsEndpoint,
        tts_api_key: formData.ttsApiKey,
        tts_voice: formData.ttsVoice,
        auto_play_audio: formData.autoPlayAudio,
        max_retries: formData.maxRetries
      })
      
      onSave(formData)
      showToast('Settings saved successfully', 'success')
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error)
      if (errorMsg.includes('Failed to fetch') || errorMsg.includes('NetworkError')) {
        showToast('Python backend unavailable. Start the Python API server first.', 'error')
      } else {
        showToast(`Failed to save settings: ${errorMsg}`, 'error')
      }
      // Don't close modal on error - let user retry
      return
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-lg rounded-lg bg-background border border-border shadow-lg">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-semibold">Settings</h2>
          <button
            onClick={onClose}
            aria-label="Close settings"
            className="p-1 rounded hover:bg-muted transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex border-b border-border">
          <button
            onClick={() => setActiveTab('chat')}
            className={cn(
              "flex-1 py-3 text-sm font-medium transition-colors",
              activeTab === 'chat'
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Chat API
          </button>
          <button
            onClick={() => setActiveTab('tts')}
            className={cn(
              "flex-1 py-3 text-sm font-medium transition-colors",
              activeTab === 'tts'
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Text-to-Speech
          </button>
          <button
            onClick={() => setActiveTab('system')}
            className={cn(
              "flex-1 py-3 text-sm font-medium transition-colors",
              activeTab === 'system'
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            System Info
          </button>
          <button
            onClick={() => setActiveTab('behavior')}
            className={cn(
              "flex-1 py-3 text-sm font-medium transition-colors",
              activeTab === 'behavior'
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Behavior
          </button>
          <button
            onClick={() => setActiveTab('data')}
            className={cn(
              "flex-1 py-3 text-sm font-medium transition-colors",
              activeTab === 'data'
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Data
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col">
          <div className="p-4 space-y-4 max-h-[60vh] overflow-y-auto">
          {activeTab === 'chat' ? (
            <>
              <div>
                <label className="block text-sm font-medium mb-1.5">
                  API Endpoint
                </label>
                <input
                  type="url"
                  value={formData.chatEndpoint}
                  onChange={(e) => setFormData({ ...formData, chatEndpoint: e.target.value })}
                  placeholder="https://api.openai.com/v1/chat/completions"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  OpenAI-compatible chat completions endpoint
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1.5">
                  API Key (Optional)
                </label>
                <div className="relative">
                  <input
                    type={showChatKey ? 'text' : 'password'}
                    value={formData.chatApiKey}
                    onChange={(e) => setFormData({ ...formData, chatApiKey: e.target.value })}
                    placeholder="sk-..."
                    className="w-full rounded-md border border-input bg-background px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <button
                    type="button"
                    onClick={() => setShowChatKey(!showChatKey)}
                    aria-label={showChatKey ? "Hide API key" : "Show API key"}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showChatKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-sm font-medium">
                    Model
                  </label>
                  <button
                    type="button"
                    onClick={loadModels}
                    disabled={loadingModels}
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
                  >
                    <RefreshCw className={cn("w-3 h-3", loadingModels && "animate-spin")} />
                    {loadingModels ? 'Loading...' : 'Refresh'}
                  </button>
                </div>
                {models.length > 0 ? (
                  <select
                    value={formData.chatModel}
                    onChange={(e) => setFormData({ ...formData, chatModel: e.target.value })}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  >
                    {models.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={formData.chatModel}
                    onChange={(e) => setFormData({ ...formData, chatModel: e.target.value })}
                    placeholder="gpt-3.5-turbo"
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                )}
              </div>

              <div>
                <label className="block text-sm font-medium mb-1.5">
                  Max Response Tokens
                </label>
                <input
                  type="number"
                  value={formData.chatContextLength}
                  onChange={(e) => setFormData({ ...formData, chatContextLength: parseInt(e.target.value) || 4096 })}
                  placeholder="4096"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  Maximum tokens in AI response
                </p>
              </div>
            </>
          ) : activeTab === 'system' ? (
            <div className="space-y-6">
              {/* System Prompt Panel */}
              <div className="border border-border rounded-lg p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileJson className="w-4 h-4 text-muted-foreground" />
                    <h3 className="text-sm font-medium">System Prompt</h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground" id="allow-editing-label">Allow editing</span>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={formData.systemPromptEditable}
                      aria-labelledby="allow-editing-label"
                      onClick={() => setFormData({ ...formData, systemPromptEditable: !formData.systemPromptEditable })}
                      className={cn(
                        "relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                        formData.systemPromptEditable ? "bg-primary" : "bg-muted"
                      )}
                    >
                      <span
                        className={cn(
                          "inline-block h-3 w-3 transform rounded-full bg-background transition-transform",
                          formData.systemPromptEditable ? "translate-x-5" : "translate-x-1"
                        )}
                      />
                    </button>
                  </div>
                </div>
                <textarea
                  value={formData.systemPrompt}
                  onChange={(e) => setFormData({ ...formData, systemPrompt: e.target.value })}
                  placeholder="You are a helpful assistant."
                  rows={6}
                  readOnly={!formData.systemPromptEditable}
                  className={cn(
                    "w-full rounded-md border border-input px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring",
                    formData.systemPromptEditable
                      ? "bg-background"
                      : "bg-muted/50 text-muted-foreground cursor-not-allowed"
                  )}
                />
                {!formData.systemPromptEditable && (
                  <p className="text-xs text-muted-foreground">
                    System prompt is locked. Enable "Allow editing" to modify.
                  </p>
                )}
              </div>

              {/* System Info Panel */}
              <div className="border border-border rounded-lg p-4 space-y-3">
                <div className="flex items-start gap-2">
                  <Server className="w-4 h-4 text-muted-foreground mt-0.5" />
                  <div>
                    <p className="text-sm font-medium">System Information Collection</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      This information is automatically collected at startup and sent to the AI with every request to help it understand the remote environment.
                    </p>
                  </div>
                </div>

                {!systemInfo?.collected ? (
                  <div className="p-4 text-center text-muted-foreground bg-muted/30 rounded">
                    <p className="text-sm">System information not collected yet.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                  {/* Operating System */}
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-muted-foreground">Operating System</h4>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="p-2 bg-muted/30 rounded">
                        <span className="text-xs text-muted-foreground">OS</span>
                        <p className="font-mono">{systemInfo.os}</p>
                      </div>
                      <div className="p-2 bg-muted/30 rounded">
                        <span className="text-xs text-muted-foreground">Kernel</span>
                        <p className="font-mono">{systemInfo.kernel}</p>
                      </div>
                      <div className="p-2 bg-muted/30 rounded">
                        <span className="text-xs text-muted-foreground">Architecture</span>
                        <p className="font-mono">{systemInfo.arch}</p>
                      </div>
                      <div className="p-2 bg-muted/30 rounded">
                        <span className="text-xs text-muted-foreground">Package Manager</span>
                        <p className="font-mono">{systemInfo.packageManager}</p>
                      </div>
                    </div>
                  </div>

                  {/* User & Environment */}
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-muted-foreground">User & Environment</h4>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="p-2 bg-muted/30 rounded">
                        <span className="text-xs text-muted-foreground">Current User</span>
                        <p className="font-mono">{systemInfo.user}</p>
                      </div>
                      <div className="p-2 bg-muted/30 rounded">
                        <span className="text-xs text-muted-foreground">Home Directory</span>
                        <p className="font-mono">{systemInfo.home}</p>
                      </div>
                      <div className="p-2 bg-muted/30 rounded">
                        <span className="text-xs text-muted-foreground">Shell</span>
                        <p className="font-mono">{systemInfo.shell}</p>
                      </div>
                      <div className="p-2 bg-muted/30 rounded">
                        <span className="text-xs text-muted-foreground">Sudo Access</span>
                        <p className="font-mono">{systemInfo.hasSudo ? 'Yes' : 'No'}</p>
                      </div>
                    </div>
                  </div>

                  {/* Installed Tools */}
                  <div className="space-y-2">
                    <h4 className="text-sm font-medium text-muted-foreground">Installed Tools</h4>
                    <div className="grid grid-cols-3 gap-2 text-sm">
                      <div className="p-2 bg-muted/30 rounded">
                        <span className="text-xs text-muted-foreground">Python</span>
                        <p className="font-mono text-xs">{systemInfo.pythonVersion}</p>
                      </div>
                      <div className="p-2 bg-muted/30 rounded">
                        <span className="text-xs text-muted-foreground">Node.js</span>
                        <p className="font-mono text-xs">{systemInfo.nodeVersion}</p>
                      </div>
                      <div className="p-2 bg-muted/30 rounded">
                        <span className="text-xs text-muted-foreground">Docker</span>
                        <p className="font-mono text-xs">{systemInfo.dockerVersion}</p>
                      </div>
                    </div>
                  </div>

                  <p className="text-xs text-muted-foreground">
                    This data helps the AI choose appropriate commands (e.g., using apt vs yum, knowing when sudo is available).
                  </p>
                </div>
              )}
              </div>
            </div>
          ) : activeTab === 'behavior' ? (
            <div className="space-y-6">
              {/* Behavior Settings Panel */}
              <div className="border border-border rounded-lg p-4 space-y-4">
                <div className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-muted-foreground" />
                  <h3 className="text-sm font-medium">Agent Behavior</h3>
                </div>
                
                {/* Max Retries Control */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">
                      Max Retry Attempts per Step
                    </label>
                    <span className="text-sm font-mono bg-muted px-2 py-1 rounded">
                      {formData.maxRetries >= 1000 ? '∞' : formData.maxRetries}
                    </span>
                  </div>
                  
                  {/* Infinite Mode Checkbox */}
                  <div className="flex items-center justify-between">
                    <label className="text-sm text-muted-foreground" id="infinite-retries-label">
                      Infinite retries (disable circuit breaker)
                    </label>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={formData.maxRetries >= 1000}
                      aria-labelledby="infinite-retries-label"
                      onClick={() => setFormData({ 
                        ...formData, 
                        maxRetries: formData.maxRetries >= 1000 ? 999 : 1000 
                      })}
                      className={cn(
                        "relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                        formData.maxRetries >= 1000 ? "bg-primary" : "bg-muted"
                      )}
                    >
                      <span
                        className={cn(
                          "inline-block h-3 w-3 transform rounded-full bg-background transition-transform",
                          formData.maxRetries >= 1000 ? "translate-x-5" : "translate-x-1"
                        )}
                      />
                    </button>
                  </div>
                  
                  {/* Slider - disabled in infinite mode */}
                  {formData.maxRetries < 1000 && (
                    <div className="space-y-2">
                      <input
                        type="range"
                        min="1"
                        max="999"
                        value={formData.maxRetries}
                        onChange={(e) => setFormData({ 
                          ...formData, 
                          maxRetries: parseInt(e.target.value) || 1 
                        })}
                        className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                      />
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">1</span>
                        <span className="text-xs text-muted-foreground flex-1 text-center">500</span>
                        <span className="text-xs text-muted-foreground">999</span>
                      </div>
                    </div>
                  )}
                  
                  {/* Number input - shown when not in infinite mode */}
                  {formData.maxRetries < 1000 && (
                    <div className="flex items-center gap-2">
                      <label className="text-sm text-muted-foreground">Value:</label>
                      <input
                        type="number"
                        min="1"
                        max="999"
                        value={formData.maxRetries}
                        onChange={(e) => {
                          const val = parseInt(e.target.value) || 1;
                          setFormData({ 
                            ...formData, 
                            maxRetries: Math.min(999, Math.max(1, val))
                          });
                        }}
                        className="w-20 rounded-md border border-input bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                      />
                    </div>
                  )}
                  
                  <p className="text-xs text-muted-foreground pt-2">
                    How many times a failed step will retry before skipping.
                    Enable "Infinite" to retry until success (useful for debugging).
                  </p>
                </div>
              </div>
            </div>
          ) : activeTab === 'data' ? (
            <div className="space-y-6">
              {/* Data Management Panel */}
              <div className="border border-border rounded-lg p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-muted-foreground" />
                  <h3 className="text-sm font-medium">Data Management</h3>
                </div>
                <p className="text-xs text-muted-foreground">
                  Export, import, or diagnose your chat data. Useful for transferring chats between ports or backing up.
                </p>

                {/* Storage Location */}
                <div className="space-y-2 pt-2 border-t border-border">
                  <label className="block text-sm font-medium">Storage Location</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value="~/.rogius/chats/ (Shared file storage)"
                      readOnly
                      className="flex-1 rounded-md border border-input bg-muted/50 px-3 py-2 text-sm text-muted-foreground"
                    />
                    <button
                      onClick={async () => {
                        const info = await getStorageInfo()
                        if (info) {
                          showToast(
                            `Storage: ${info.location} • ${info.chatCount} chats • ${info.totalSizeKB} KB`,
                            'info'
                          )
                        } else {
                          showToast('Failed to get storage information', 'error')
                        }
                      }}
                      className="px-3 py-2 text-sm bg-muted text-foreground rounded hover:bg-muted/80 transition-colors"
                    >
                      Info
                    </button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    All ports (3000, 3001, etc.) now share the same chat history via file storage.
                  </p>
                </div>

                {/* Clear All History */}
                <div className="pt-3 border-t border-border">
                  <button
                    onClick={async () => {
                      const confirmed = confirm(
                        'WARNING: This will delete ALL chat history permanently.\n\n' +
                        'This action cannot be undone.\n\n' +
                        'Are you sure you want to continue?'
                      )
                      if (confirmed) {
                        try {
                          await clearAllChats()
                          showToast('All chat history has been cleared', 'success')
                          setTimeout(() => window.location.reload(), 1500)
                        } catch (error) {
                          showToast('Failed to clear chat history: ' + (error as Error).message, 'error')
                        }
                      }
                    }}
                    className="flex items-center gap-2 px-3 py-2 text-sm bg-destructive text-destructive-foreground rounded hover:bg-destructive/90 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    Clear All History
                  </button>
                </div>

                <div className="flex flex-wrap gap-2 pt-2">
                  <button
                    id="export-chats-btn"
                    onClick={async () => {
                      const { getAllChats } = await import('@/lib/chat-storage')
                      const chats = await getAllChats()
                      const exportData = {
                        version: 'rogius-export-v1',
                        exportedAt: Date.now(),
                        port: window.location.port,
                        chats
                      }
                      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
                      const url = URL.createObjectURL(blob)
                      const a = document.createElement('a')
                      a.href = url
                      a.download = `rogius-chats-${Date.now()}.json`
                      a.click()
                      URL.revokeObjectURL(url)
                    }}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/90 transition-colors"
                  >
                    <Download className="w-4 h-4" />
                    Export Chats
                  </button>
                  <label className="flex items-center gap-2 px-3 py-1.5 text-sm bg-muted text-foreground rounded hover:bg-muted/80 transition-colors cursor-pointer">
                    <Upload className="w-4 h-4" />
                    Import Chats
                    <input
                      type="file"
                      accept=".json"
                      className="hidden"
                      onChange={async (e) => {
                        const file = e.target.files?.[0]
                        if (!file) return
                        const reader = new FileReader()
                        reader.onload = async (ev) => {
                          try {
                            const { saveChat } = await import('@/lib/chat-storage')
                            const data = JSON.parse(ev.target?.result as string)
                            if (data.chats && Array.isArray(data.chats)) {
                              let imported = 0
                              for (const chat of data.chats) {
                                if (chat.id) {
                                  chat.updatedAt = Date.now()
                                  await saveChat(chat)
                                  imported++
                                }
                              }
                              showToast(`Imported ${imported} chats successfully!`, 'success')
                              setTimeout(() => window.location.reload(), 1500)
                            } else {
                              showToast('Invalid export file format', 'error')
                            }
                          } catch (err) {
                            showToast('Failed to parse import file', 'error')
                          }
                        }
                        reader.readAsText(file)
                      }}
                    />
                  </label>
                  <button
                    onClick={async () => {
                      const { getStorageInfo, getAllChats } = await import('@/lib/chat-storage')
                      const info = await getStorageInfo()
                      const chats = await getAllChats()
                      if (info) {
                        const report = `Storage Diagnostic Report

Location: ${info.location}
Total Chats: ${info.chatCount}
Total Size: ${info.totalSizeKB} KB

Chat Files:
${chats.map(c => `  ${c.id}.json: ${c.title.substring(0, 30)} (${c.messages.length} messages)`).join('\n')}`
                        // Show first few chat files in toast
                        const preview = chats.slice(0, 3).map(c => c.title.substring(0, 20)).join(', ')
                        const more = chats.length > 3 ? ` and ${chats.length - 3} more` : ''
                        showToast(`Storage: ${info.location} • ${info.chatCount} chats`, 'info')
                      } else {
                        showToast('Failed to get storage information', 'error')
                      }
                    }}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm bg-muted text-foreground rounded hover:bg-muted/80 transition-colors"
                  >
                    <FileJson className="w-4 h-4" />
                    Diagnostics
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-sm font-medium mb-1.5">
                  TTS Endpoint
                </label>
                <input
                  type="url"
                  value={formData.ttsEndpoint}
                  onChange={(e) => setFormData({ ...formData, ttsEndpoint: e.target.value })}
                  placeholder="http://localhost:8880/v1/audio/speech"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  KokoroTTS or compatible TTS endpoint
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1.5">
                  TTS API Key (optional)
                </label>
                <div className="relative">
                  <input
                    type={showTtsKey ? 'text' : 'password'}
                    value={formData.ttsApiKey}
                    onChange={(e) => setFormData({ ...formData, ttsApiKey: e.target.value })}
                    placeholder="Leave empty if no auth required"
                    className="w-full rounded-md border border-input bg-background px-3 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                  <button
                    type="button"
                    onClick={() => setShowTtsKey(!showTtsKey)}
                    aria-label={showTtsKey ? "Hide TTS API key" : "Show TTS API key"}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showTtsKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1.5">
                  Voice
                </label>
                <input
                  type="text"
                  value={formData.ttsVoice}
                  onChange={(e) => setFormData({ ...formData, ttsVoice: e.target.value })}
                  placeholder="af_bella"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  KokoroTTS voice code (e.g., af_bella, af_sarah, am_adam)
                </p>
              </div>

              <div className="flex items-center justify-between pt-4">
                <label className="text-sm font-medium" id="auto-play-audio-label">
                  Auto-play audio for assistant responses
                </label>
                <button
                  type="button"
                  role="switch"
                  aria-checked={formData.autoPlayAudio}
                  aria-labelledby="auto-play-audio-label"
                  onClick={() => setFormData({ ...formData, autoPlayAudio: !formData.autoPlayAudio })}
                  className={cn(
                    "relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                    formData.autoPlayAudio ? "bg-primary" : "bg-muted"
                  )}
                >
                  <span
                    className={cn(
                      "inline-block h-4 w-4 transform rounded-full bg-background transition-transform",
                      formData.autoPlayAudio ? "translate-x-6" : "translate-x-1"
                    )}
                  />
                </button>
              </div>
            </>
          )}
          </div>

          <div className="flex justify-end gap-2 p-4 pt-4 border-t border-border">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-md border border-input bg-background text-sm font-medium hover:bg-muted transition-colors"
            >
              Close
            </button>
            {activeTab !== 'system' && activeTab !== 'data' && (
              <button
                type="submit"
                disabled={isSaving}
                className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSaving ? 'Saving...' : 'Save Settings'}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
