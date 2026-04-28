'use client'

import { useState, useEffect, useCallback } from 'react'

const POLL_INTERVAL = 5000 // Check every 5 seconds
const STALE_THRESHOLD = 10000 // Consider status stale after 10 seconds
const PYTHON_PORT = process.env.NEXT_PUBLIC_PYTHON_API_URL?.split(':').pop() || '8000'

export interface UsePythonServerReturn {
  isRunning: boolean
  isChecking: boolean
  isStarting: boolean
  isStale: boolean  // True if last health check is old
  port: string
  startServer: () => Promise<void>
  restartServer: () => Promise<void>
  checkHealth: () => Promise<void>  // Expose for manual checks before critical ops
}

export function usePythonServer(): UsePythonServerReturn {
  const [isRunning, setIsRunning] = useState(false)
  const [isChecking, setIsChecking] = useState(true)
  const [isStarting, setIsStarting] = useState(false)
  const [lastChecked, setLastChecked] = useState<number>(0)

  const isStale = Date.now() - lastChecked > STALE_THRESHOLD

  const checkHealth = useCallback(async () => {
    try {
      // Use Next.js API route to avoid CORS issues with direct connection
      const response = await fetch('/api/python/health', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      })
      setIsRunning(response.ok)
      setLastChecked(Date.now())
    } catch {
      setIsRunning(false)
      setLastChecked(Date.now())
    } finally {
      setIsChecking(false)
    }
  }, [])

  // Start server function (defined before useEffect)
  const startServer = useCallback(async (force = false) => {
    if ((isRunning || isStarting) && !force) return

    setIsStarting(true)
    try {
      // Call the Next.js API route to start the Python server
      const response = await fetch('/api/python/start', {
        method: 'POST',
      })

      if (response.ok) {
        // Wait a moment for the server to start, then check health
        await new Promise((resolve) => setTimeout(resolve, 2000))
        await checkHealth()
      } else {
        const error = await response.json().catch(() => ({ error: 'Failed to start' }))
        console.error('Failed to start Python server:', error)
      }
    } catch (error) {
      console.error('Error starting Python server:', error)
    } finally {
      setIsStarting(false)
    }
  }, [isRunning, isStarting, checkHealth])

  // Poll for server status and auto-start on mount
  useEffect(() => {
    const init = async () => {
      await checkHealth()
      // Auto-start if not running (only on initial mount)
      if (!isRunning && !isStarting) {
        console.log('[PythonServer] Auto-starting Python backend...')
        await startServer(false)
      }
    }
    init()
    const interval = setInterval(checkHealth, POLL_INTERVAL)
    return () => clearInterval(interval)
  }, []) // Empty deps - run once on mount

  const restartServer = useCallback(async () => {
    if (isStarting) return

    setIsStarting(true)
    try {
      // Stop first if running
      if (isRunning) {
        await fetch('/api/python/stop', { method: 'POST' })
        // Wait for server to fully stop
        await new Promise((resolve) => setTimeout(resolve, 1000))
      }

      // Then start
      await startServer(true)
    } catch (error) {
      console.error('Error restarting Python server:', error)
    }
    // Note: isStarting is reset by startServer's finally block
  }, [isStarting, isRunning, startServer])

  return {
    isRunning,
    isChecking,
    isStarting,
    isStale,
    port: PYTHON_PORT,
    startServer: () => startServer(false),
    restartServer,
    checkHealth,
  }
}
