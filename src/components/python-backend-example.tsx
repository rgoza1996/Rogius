/**
 * Example: Using Python Backend from React
 * 
 * This component demonstrates how the webapp can use the
 * Python TUI modules through the HTTP API.
 */
'use client'

import { useState, useCallback } from 'react'
import { pythonBridge } from '@/lib/python-bridge'

export function PythonBackendExample() {
  const [output, setOutput] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [pythonConnected, setPythonConnected] = useState<boolean | null>(null)

  // Check if Python backend is running
  const checkConnection = useCallback(async () => {
    try {
      const health = await pythonBridge.health()
      setPythonConnected(health.status === 'healthy')
      setOutput(`Python backend connected! Version: ${health.version}`)
    } catch (error) {
      setPythonConnected(false)
      setOutput('Python backend not running. Start it with: npm run python-api:start')
    }
  }, [])

  // Execute terminal command via Python
  const runTerminalCommand = useCallback(async () => {
    setLoading(true)
    try {
      const result = await pythonBridge.terminal.execute({
        command: 'echo "Hello from Python backend!"',
        cwd: '.'
      })
      setOutput(
        `Command: ${result.command}\n` +
        `Exit Code: ${result.exit_code}\n` +
        `Shell: ${result.shell_used}\n` +
        `Output: ${result.stdout}`
      )
    } catch (error) {
      setOutput(`Error: ${error}`)
    }
    setLoading(false)
  }, [])

  // Create and execute multi-step plan
  const runMultistepPlan = useCallback(async () => {
    setLoading(true)
    try {
      // Create plan
      const plan = await pythonBridge.multistep.create({
        goal: 'Example multi-step task',
        steps: [
          { description: 'Say hello', command: 'echo "Step 1: Hello"' },
          { description: 'Show date', command: 'date' },
          { description: 'List files', command: 'ls' }
        ]
      })
      
      setOutput(`Plan created: ${plan.plan_id} (${plan.steps_count} steps)\n\nExecuting...\n`)
      
      // Execute plan
      const result = await pythonBridge.multistep.execute()
      
      setOutput(prev => 
        prev + `\nPlan completed!\n` +
        `Status: ${result.status}\n` +
        `Progress: ${result.completed}/${result.total} (${result.percentage}%)`
      )
    } catch (error) {
      setOutput(`Error: ${error}`)
    }
    setLoading(false)
  }, [])

  // Get system info
  const getSystemInfo = useCallback(async () => {
    setLoading(true)
    try {
      const info = await pythonBridge.system.info()
      setOutput(
        `System Information (from Python):\n\n` +
        `OS: ${info.os} ${info.os_version}\n` +
        `Architecture: ${info.architecture}\n` +
        `Shell: ${info.shell}\n` +
        `Python: ${info.python_version}\n` +
        `Working Directory: ${info.working_directory}\n` +
        `Hostname: ${info.hostname}\n` +
        `Username: ${info.username}`
      )
    } catch (error) {
      setOutput(`Error: ${error}`)
    }
    setLoading(false)
  }, [])

  // AI Chat example
  const runAIChat = useCallback(async () => {
    setLoading(true)
    setOutput('Streaming AI response...\n\n')
    
    try {
      await pythonBridge.ai.chatStream(
        {
          messages: [
            { role: 'system', content: 'You are a helpful assistant.' },
            { role: 'user', content: 'Say "Hello from Python AI backend!" and nothing else.' }
          ],
          enable_tools: false,
          stream: true
        },
        (chunk) => {
          if (chunk.content) {
            setOutput(prev => prev + chunk.content)
          }
        },
        () => {
          setOutput(prev => prev + '\n\n[Stream complete]')
          setLoading(false)
        }
      )
    } catch (error) {
      setOutput(`Error: ${error}`)
      setLoading(false)
    }
  }, [])

  return (
    <div className="p-6 bg-gray-900 rounded-lg">
      <h2 className="text-xl font-bold mb-4 text-white">
        Python Backend Integration Example
      </h2>
      
      <div className="mb-4 flex gap-2 flex-wrap">
        <button
          onClick={checkConnection}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
        >
          Check Connection
        </button>
        
        <button
          onClick={getSystemInfo}
          disabled={loading}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
        >
          System Info
        </button>
        
        <button
          onClick={runTerminalCommand}
          disabled={loading}
          className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
        >
          Run Command
        </button>
        
        <button
          onClick={runMultistepPlan}
          disabled={loading}
          className="px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700 disabled:opacity-50"
        >
          Multi-Step Plan
        </button>
        
        <button
          onClick={runAIChat}
          disabled={loading}
          className="px-4 py-2 bg-pink-600 text-white rounded hover:bg-pink-700 disabled:opacity-50"
        >
          AI Chat
        </button>
      </div>
      
      {pythonConnected !== null && (
        <div className={`mb-4 p-2 rounded ${
          pythonConnected ? 'bg-green-900 text-green-200' : 'bg-red-900 text-red-200'
        }`}>
          {pythonConnected ? '✓ Python backend connected' : '✗ Python backend disconnected'}
        </div>
      )}
      
      {output && (
        <pre className="p-4 bg-black text-green-400 rounded overflow-auto max-h-96 text-sm">
          {output}
        </pre>
      )}
      
      <div className="mt-4 text-sm text-gray-400">
        <p>Python API URL: <code className="bg-gray-800 px-1">http://127.0.0.1:8000</code></p>
        <p>Start server: <code className="bg-gray-800 px-1">npm run python-api:start</code></p>
        <p>API docs: <a href="http://127.0.0.1:8000/docs" target="_blank" className="text-blue-400">http://127.0.0.1:8000/docs</a></p>
      </div>
    </div>
  )
}
