'use client'

import { useState, useCallback } from 'react'
import {
  BranchedMessage,
  generateMessageId,
} from '@/lib/chat-storage'

export interface UseBranchingReturn {
  editingMessageId: string | null
  editContent: string
  setEditContent: (content: string) => void
  copiedMessageId: string | null
  startEdit: (messageId: string, content: string) => void
  saveEdit: (
    messageIndex: number,
    messages: BranchedMessage[],
    setMessages: (messages: BranchedMessage[]) => void,
    onRegenerate: (truncatedMessages: BranchedMessage[]) => Promise<unknown>
  ) => Promise<void>
  cancelEdit: () => void
  switchBranch: (
    messageIndex: number,
    branchIndex: number,
    messages: BranchedMessage[],
    setMessages: (messages: BranchedMessage[]) => void
  ) => void
  copyToClipboard: (messageId: string, content: string) => void
}

export function useBranching(): UseBranchingReturn {
  const [editingMessageId, setEditingMessageId] = useState<string | null>(null)
  const [editContent, setEditContent] = useState('')
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)

  const startEdit = useCallback((messageId: string, content: string) => {
    setEditingMessageId(messageId)
    setEditContent(content)
  }, [])

  const cancelEdit = useCallback(() => {
    setEditingMessageId(null)
    setEditContent('')
  }, [])

  const saveEdit = useCallback(async (
    messageIndex: number,
    messages: BranchedMessage[],
    setMessages: (messages: BranchedMessage[]) => void,
    onRegenerate: (truncatedMessages: BranchedMessage[]) => Promise<unknown>
  ) => {
    const targetMessage = messages[messageIndex]
    if (!targetMessage || !editContent.trim()) return
    // Allow editing both user and assistant messages for full branching support

    // Save the current message's subtree as a branch before editing
    const subtree = messages.slice(messageIndex + 1)

    // Create new branch for this version (stores original content + its subtree)
    const newBranch = {
      messageId: targetMessage.messageId,
      content: targetMessage.content,
      timestamp: Date.now(),
      subtree: [...subtree]
    }

    // Update the message with the new branch and new content
    const updatedMessages = [...messages]
    const existingBranches = targetMessage.branches || []

    // Add new branch to existing branches, set current to edited content
    const newMessageId = generateMessageId()
    updatedMessages[messageIndex] = {
      ...targetMessage,
      content: editContent.trim(),
      messageId: newMessageId,
      branches: [...existingBranches, newBranch],
      currentBranchIndex: -1 // -1 means current (edited) version
    }

    // Update state first
    setEditingMessageId(null)
    setEditContent('')

    // Remove subsequent messages since we branched
    const truncatedMessages = updatedMessages.slice(0, messageIndex + 1)
    setMessages(truncatedMessages)

    // Generate new response
    await onRegenerate(truncatedMessages)
  }, [editContent])

  const switchBranch = useCallback((
    messageIndex: number,
    branchIndex: number,
    messages: BranchedMessage[],
    setMessages: (messages: BranchedMessage[]) => void
  ) => {
    const targetMessage = messages[messageIndex]
    if (!targetMessage?.branches?.length) return

    // -1 means "current version" (the editable one), not a saved branch
    if (branchIndex < -1 || branchIndex >= targetMessage.branches.length) return

    // Get current state before switching
    const currentSubtree = messages.slice(messageIndex + 1)
    const currentBranchIndex = targetMessage.currentBranchIndex ?? -1

    // Build updated branches - save current state if we're on current version
    let updatedBranches = [...targetMessage.branches]
    if (currentBranchIndex === -1) {
      // We're on current version, save it as a special branch
      // Use a stable ID for the "current version" slot - based on message position, not the edited messageId
      const currentVersionId = `current-${targetMessage.branches[0]?.messageId?.split('-')[1] ?? 'root'}`
      const currentAsBranch = {
        messageId: currentVersionId,
        content: targetMessage.content,
        timestamp: Date.now(),
        subtree: [...currentSubtree]
      }
      // Check if current version slot already exists
      const existingIndex = updatedBranches.findIndex(b => b.messageId === currentVersionId)
      if (existingIndex >= 0) {
        // Update existing saved current version
        updatedBranches[existingIndex] = currentAsBranch
      } else {
        // Add as new branch at the end
        updatedBranches.push(currentAsBranch)
      }
    }

    // Build new message list: messages up to target (exclusive)
    const newMessages = messages.slice(0, messageIndex)

    let selectedContent: string
    let selectedSubtree: BranchedMessage[]
    let selectedMessageId: string

    if (branchIndex === -1) {
      // Switching to current version - find the saved current state using stable ID
      const currentVersionId = `current-${targetMessage.branches[0]?.messageId?.split('-')[1] ?? 'root'}`
      const savedCurrentIndex = updatedBranches.findIndex(b => b.messageId === currentVersionId)
      if (savedCurrentIndex >= 0) {
        const savedCurrent = updatedBranches[savedCurrentIndex]
        selectedContent = savedCurrent.content
        selectedSubtree = savedCurrent.subtree
        selectedMessageId = savedCurrent.messageId
      } else {
        // No saved current state, use what we have
        selectedContent = targetMessage.content
        selectedSubtree = currentSubtree
        selectedMessageId = targetMessage.messageId
      }
    } else {
      // Saved branch version
      const branch = updatedBranches[branchIndex]
      selectedContent = branch.content
      selectedSubtree = branch.subtree
      selectedMessageId = branch.messageId
    }

    // Add the selected version as the active message
    newMessages.push({
      ...targetMessage,
      content: selectedContent,
      messageId: selectedMessageId,
      currentBranchIndex: branchIndex,
      branches: updatedBranches
    })

    // Add the selected subtree
    newMessages.push(...selectedSubtree)

    setMessages(newMessages)
  }, [])

  const copyToClipboard = useCallback((messageId: string, content: string) => {
    navigator.clipboard.writeText(content)
    setCopiedMessageId(messageId)
    setTimeout(() => setCopiedMessageId(null), 2000)
  }, [])

  return {
    editingMessageId,
    editContent,
    setEditContent,
    copiedMessageId,
    startEdit,
    saveEdit,
    cancelEdit,
    switchBranch,
    copyToClipboard,
  }
}
