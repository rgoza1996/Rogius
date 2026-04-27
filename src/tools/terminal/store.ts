'use client'

import { useState, useCallback, useEffect } from 'react'

export interface TerminalCommand {
  id: string
  command: string
  cwd: string
  status: 'pending' | 'running' | 'completed' | 'error'
  stdout: string
  stderr: string
  exitCode: number
  timestamp: number
}

export interface TerminalConfig {
  currentDirectory: string
  commandHistory: string[]
  isOpen: boolean
  securityLevel: 'auto' | 'confirm-destructive' | 'always-confirm'
}

export interface SystemInfo {
  os: string
  kernel: string
  arch: string
  user: string
  home: string
  shell: string
  packageManager: string
  hasSudo: boolean
  pythonVersion: string
  nodeVersion: string
  dockerVersion: string
  collected: boolean
}

export type TerminalState = TerminalConfig

const STORAGE_KEY = 'rogius-terminal-config'

export function getTerminalConfig(): TerminalConfig {
  if (typeof window === 'undefined') {
    return {
      currentDirectory: '.',
      commandHistory: [],
      isOpen: false,
      securityLevel: 'confirm-destructive'
    }
  }
  
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) {
    const parsed = JSON.parse(stored)
    return {
      currentDirectory: parsed.currentDirectory || '.',
      commandHistory: parsed.commandHistory || [],
      isOpen: parsed.isOpen ?? false,
      securityLevel: parsed.securityLevel || 'confirm-destructive'
    }
  }
  
  return {
    currentDirectory: '.',
    commandHistory: [],
    isOpen: false,
    securityLevel: 'confirm-destructive'
  }
}

export function saveTerminalConfig(config: Partial<TerminalConfig>) {
  if (typeof window === 'undefined') return
  
  const current = getTerminalConfig()
  const updated = { ...current, ...config }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
}

export async function collectSystemInfo(): Promise<SystemInfo> {
  const defaultInfo: SystemInfo = {
    os: 'unknown',
    kernel: 'unknown',
    arch: 'unknown',
    user: 'unknown',
    home: 'unknown',
    shell: 'unknown',
    packageManager: 'unknown',
    hasSudo: false,
    pythonVersion: 'not installed',
    nodeVersion: 'not installed',
    dockerVersion: 'not installed',
    collected: false
  }

  // Use Python backend API for system info (cross-platform: Windows/Linux/macOS)
  try {
    const pythonResponse = await fetch('/api/python/system/info', { 
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (pythonResponse.ok) {
      const pythonInfo = await pythonResponse.json()
      
      // Map Python backend response to SystemInfo format
      return {
        os: pythonInfo.os || 'unknown',
        kernel: pythonInfo.os_version || 'unknown',
        arch: pythonInfo.architecture || 'unknown',
        user: pythonInfo.username || 'unknown',
        home: pythonInfo.working_directory || 'unknown',
        shell: pythonInfo.shell || 'unknown',
        packageManager: pythonInfo.package_manager || 'unknown',
        hasSudo: pythonInfo.has_sudo || false,
        pythonVersion: pythonInfo.python_version || 'not installed',
        nodeVersion: pythonInfo.node_version || 'not installed',
        dockerVersion: pythonInfo.docker_version || 'not installed',
        collected: true
      }
    }
  } catch (pythonError) {
    console.log('Python backend system info failed:', pythonError)
  }

  return defaultInfo
}

export function useTerminal() {
  const [config, setConfig] = useState<TerminalConfig>(getTerminalConfig())
  const [commands, setCommands] = useState<TerminalCommand[]>([])
  const [isExecuting, setIsExecuting] = useState(false)
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null)
  
  const updateConfig = useCallback((updates: Partial<TerminalConfig>) => {
    setConfig(prev => {
      const updated = { ...prev, ...updates }
      saveTerminalConfig(updated)
      return updated
    })
  }, [])
  
  const setCurrentDirectory = useCallback((dir: string) => {
    updateConfig({ currentDirectory: dir })
  }, [updateConfig])
  
  const toggleTerminal = useCallback(() => {
    updateConfig({ isOpen: !config.isOpen })
  }, [config.isOpen, updateConfig])
  
  const setSecurityLevel = useCallback((level: TerminalConfig['securityLevel']) => {
    updateConfig({ securityLevel: level })
  }, [updateConfig])
  
  const addToHistory = useCallback((command: string) => {
    updateConfig({
      commandHistory: [...config.commandHistory, command].slice(-50)
    })
  }, [config.commandHistory, updateConfig])
  
  const executeCommand = useCallback(async (command: string, confirmOverride?: boolean): Promise<TerminalCommand> => {
    const id = `cmd-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    
    const newCommand: TerminalCommand = {
      id,
      command,
      cwd: config.currentDirectory,
      status: 'running',
      stdout: '',
      stderr: '',
      exitCode: 0,
      timestamp: Date.now()
    }
    
    setCommands(prev => [...prev, newCommand])
    setIsExecuting(true)
    
    try {
      const response = await fetch('/api/terminal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command,
          cwd: config.currentDirectory
        })
      })
      
      const result = await response.json()
      
      const completedCommand: TerminalCommand = {
        ...newCommand,
        status: result.exitCode === 0 ? 'completed' : 'error',
        stdout: result.stdout,
        stderr: result.stderr,
        exitCode: result.exitCode,
        cwd: result.cwd
      }
      
      setCommands(prev =>
        prev.map(cmd => cmd.id === id ? completedCommand : cmd)
      )
      
      if (result.cwd !== config.currentDirectory) {
        updateConfig({ currentDirectory: result.cwd })
      }
      
      addToHistory(command)
      
      return completedCommand
      
    } catch (error) {
      const errorCommand: TerminalCommand = {
        ...newCommand,
        status: 'error',
        stderr: String(error),
        exitCode: 1
      }
      
      setCommands(prev =>
        prev.map(cmd => cmd.id === id ? errorCommand : cmd)
      )
      
      return errorCommand
    } finally {
      setIsExecuting(false)
    }
  }, [config.currentDirectory, addToHistory, updateConfig])
  
  const clearCommands = useCallback(() => {
    setCommands([])
  }, [])
  
  // Collect system info on mount
  useEffect(() => {
    const loadSystemInfo = async () => {
      const info = await collectSystemInfo()
      setSystemInfo(info)
    }
    loadSystemInfo()
  }, [])
  
  const refreshSystemInfo = useCallback(async () => {
    const info = await collectSystemInfo()
    setSystemInfo(info)
    return info
  }, [])
  
  return {
    config,
    commands,
    isExecuting,
    systemInfo,
    refreshSystemInfo,
    setCurrentDirectory,
    toggleTerminal,
    setSecurityLevel,
    executeCommand,
    clearCommands,
    addToHistory
  }
}

export function getCurrentDirectory(): string {
  return getTerminalConfig().currentDirectory
}

export function setDirectory(dir: string) {
  saveTerminalConfig({ currentDirectory: dir })
}
