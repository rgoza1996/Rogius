'use client'

import { useState, useEffect, useCallback, useRef } from 'react'

const PYTHON_API_BASE = process.env.NEXT_PUBLIC_PYTHON_API_URL || 'http://127.0.0.1:8000'
const KOKORO_PORT = '8880' // Default port, will be extracted from endpoint if available
const POLL_INTERVAL = 5000 // 5 seconds
const STARTUP_TIMEOUT = 5 * 60 * 1000 // 5 minutes

export interface UseKokoroServerReturn {
  isAvailable: boolean
  isChecking: boolean
  isStarting: boolean
  isPolling: boolean
  port: string
  startServer: () => Promise<void>
  restartServer: () => Promise<void>
}

export function useKokoroServer(): UseKokoroServerReturn {
  const [isAvailable, setIsAvailable] = useState(false)
  const [isChecking, setIsChecking] = useState(true)
  const [isStarting, setIsStarting] = useState(false)
  const [isPolling, setIsPolling] = useState(false)
  const [port, setPort] = useState(KOKORO_PORT)
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Check Kokoro server status via Python backend
  const checkStatus = useCallback(async () => {
    try {
      const response = await fetch(`${PYTHON_API_BASE}/tts/check`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      })

      if (response.ok) {
        const data = await response.json()
        setIsAvailable(data.available)
        // Extract port from endpoint URL (e.g., "http://100.71.89.62:8880/v1/audio/speech")
        if (data.endpoint) {
          const portMatch = data.endpoint.match(/:(\d+)/)
          if (portMatch) {
            setPort(portMatch[1])
          }
        }
        return data.available
      } else {
        setIsAvailable(false)
        return false
      }
    } catch {
      setIsAvailable(false)
      return false
    } finally {
      setIsChecking(false)
    }
  }, [])

  // Stop polling
  const stopPolling = useCallback(() => {
    console.log('[KokoroServer] Stopping polling')
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current)
      pollingIntervalRef.current = null
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    setIsPolling(false)
  }, [])

  // Start polling during startup
  const startPolling = useCallback(() => {
    // Clear any existing intervals/timeouts first (without using stopPolling to avoid state race)
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current)
      pollingIntervalRef.current = null
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = null
    }
    
    console.log('[KokoroServer] Starting polling every 5 seconds')
    setIsPolling(true)
    
    // Do an immediate first check
    checkStatus().then(available => {
      if (available) {
        console.log('[KokoroServer] Server already available, stopping poll')
        stopPolling()
      }
    })
    
    // Start polling every 5 seconds
    pollingIntervalRef.current = setInterval(() => {
      console.log('[KokoroServer] Polling check...')
      checkStatus().then(available => {
        if (available) {
          console.log('[KokoroServer] Server is now available!')
          stopPolling()
        } else {
          console.log('[KokoroServer] Server not yet available')
        }
      })
    }, POLL_INTERVAL)
    
    // 5-minute timeout
    timeoutRef.current = setTimeout(() => {
      console.log('[KokoroServer] Startup timeout reached (5 minutes)')
      stopPolling()
    }, STARTUP_TIMEOUT)
  }, [checkStatus, stopPolling])

  // Start server function
  const startServer = useCallback(async (force = false) => {
    if ((isAvailable || isStarting) && !force) return

    setIsStarting(true)
    try {
      const response = await fetch('/api/kokoro/start', {
        method: 'POST',
      })

      if (response.ok) {
        // Start polling to monitor startup progress
        startPolling()
      } else {
        const error = await response.json().catch(() => ({ error: 'Failed to start' }))
        console.error('Failed to start Kokoro server:', error)
      }
    } catch (error) {
      console.error('Error starting Kokoro server:', error)
    } finally {
      setIsStarting(false)
    }
  }, [isAvailable, isStarting, startPolling])

  // Check status on mount only (no polling until user starts server)
  useEffect(() => {
    checkStatus()
    // Cleanup on unmount
    return () => stopPolling()
  }, [checkStatus, stopPolling])

  const restartServer = useCallback(async () => {
    if (isStarting || isPolling) return

    setIsStarting(true)
    try {
      // Note: Kokoro doesn't have a stop endpoint yet, so we just restart
      // In the future, could add /api/kokoro/stop endpoint
      
      // Stop any existing polling
      stopPolling()
      
      // Start the server and begin polling
      const response = await fetch('/api/kokoro/start', {
        method: 'POST',
      })

      if (response.ok) {
        startPolling()
      }
    } catch (error) {
      console.error('Error restarting Kokoro server:', error)
    } finally {
      setIsStarting(false)
    }
  }, [isStarting, isPolling, startPolling, stopPolling])

  return {
    isAvailable,
    isChecking,
    isStarting,
    isPolling,
    port,
    startServer: () => startServer(false),
    restartServer,
  }
}
