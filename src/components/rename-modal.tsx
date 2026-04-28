'use client'

import { useState, useEffect, useCallback } from 'react'
import { X, Sparkles, Check } from 'lucide-react'

interface RenameModalProps {
  isOpen: boolean
  chatId: string
  currentTitle: string
  onClose: () => void
  onSubmit: (newTitle: string) => void
  onRenamer: () => void
}

export function RenameModal({ isOpen, chatId, currentTitle, onClose, onSubmit, onRenamer }: RenameModalProps) {
  const [title, setTitle] = useState(currentTitle)
  const [isProcessing, setIsProcessing] = useState(false)

  // Reset title when modal opens
  useEffect(() => {
    if (isOpen) {
      setTitle(currentTitle)
    }
  }, [isOpen, currentTitle])

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  const handleSubmit = useCallback(() => {
    if (title.trim()) {
      setIsProcessing(true)
      onSubmit(title.trim())
      setIsProcessing(false)
    }
  }, [title, onSubmit])

  const handleRenamer = useCallback(() => {
    setIsProcessing(true)
    onRenamer()
    setIsProcessing(false)
  }, [onRenamer])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSubmit()
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative bg-background border border-border rounded-lg shadow-lg p-6 w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Rename Chat</h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-muted transition-colors"
            disabled={isProcessing}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-1">
              Chat Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full px-3 py-2 bg-background border border-input rounded-md focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Enter chat title..."
              autoFocus
              disabled={isProcessing}
            />
          </div>

          {/* Buttons */}
          <div className="flex items-center gap-2 pt-2">
            <button
              onClick={handleSubmit}
              disabled={!title.trim() || isProcessing}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Check className="w-4 h-4" />
              Submit
            </button>
            
            <button
              onClick={handleRenamer}
              disabled={isProcessing}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Sparkles className="w-4 h-4" />
              Renamer
            </button>
            
            <button
              onClick={onClose}
              disabled={isProcessing}
              className="px-4 py-2 border border-border rounded-md hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>

        {/* Info text */}
        <p className="text-xs text-muted-foreground mt-4">
          <strong>Submit:</strong> Manually set title (chat becomes ineligible for auto-rename)
          <br />
          <strong>Renamer:</strong> Let AI generate a title (chat becomes eligible for auto-rename)
        </p>
      </div>
    </div>
  )
}
