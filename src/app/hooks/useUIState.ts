'use client'

import { useState, useRef, useEffect } from 'react'

export interface UseUIStateReturn {
  // Settings modal
  showSettings: boolean
  setShowSettings: (value: boolean) => void
  openSettings: () => void
  closeSettings: () => void

  // Sidebar
  sidebarOpen: boolean
  setSidebarOpen: (value: boolean) => void
  toggleSidebar: () => void
  closeSidebar: () => void

  // Terminal dropdown
  terminalDropdownOpen: boolean
  setTerminalDropdownOpen: (value: boolean) => void
  openTerminalDropdown: () => void
  closeTerminalDropdown: () => void
  toggleTerminalDropdown: () => void
  terminalDropdownRef: React.RefObject<HTMLDivElement>

  // Chat copied feedback
  chatCopied: boolean
  setChatCopied: (value: boolean) => void
  triggerChatCopied: () => void
}

export function useUIState(): UseUIStateReturn {
  // Settings modal state
  const [showSettings, setShowSettings] = useState(false)

  // Sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Terminal dropdown state
  const [terminalDropdownOpen, setTerminalDropdownOpen] = useState(false)
  const terminalDropdownRef = useRef<HTMLDivElement>(null)

  // Clipboard feedback state
  const [chatCopied, setChatCopied] = useState(false)

  // Close terminal dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        terminalDropdownRef.current &&
        !terminalDropdownRef.current.contains(event.target as Node)
      ) {
        setTerminalDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Auto-reset chat copied after 2 seconds
  useEffect(() => {
    if (chatCopied) {
      const timer = setTimeout(() => setChatCopied(false), 2000)
      return () => clearTimeout(timer)
    }
  }, [chatCopied])

  // Convenience actions
  const openSettings = () => setShowSettings(true)
  const closeSettings = () => setShowSettings(false)
  const toggleSidebar = () => setSidebarOpen((prev) => !prev)
  const closeSidebar = () => setSidebarOpen(false)
  const openTerminalDropdown = () => setTerminalDropdownOpen(true)
  const closeTerminalDropdown = () => setTerminalDropdownOpen(false)
  const toggleTerminalDropdown = () => setTerminalDropdownOpen((prev) => !prev)
  const triggerChatCopied = () => setChatCopied(true)

  return {
    showSettings,
    setShowSettings,
    openSettings,
    closeSettings,
    sidebarOpen,
    setSidebarOpen,
    toggleSidebar,
    closeSidebar,
    terminalDropdownOpen,
    setTerminalDropdownOpen,
    openTerminalDropdown,
    closeTerminalDropdown,
    toggleTerminalDropdown,
    terminalDropdownRef,
    chatCopied,
    setChatCopied,
    triggerChatCopied,
  }
}
