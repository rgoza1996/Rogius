'use client'

import { useState, useEffect } from 'react'
import { Plus, Trash2, MessageSquare, X, Edit2, Check, Menu } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ChatSession, getAllChats, deleteChat, updateChatTitle, triggerRenamer, toggleChatEligibility } from '@/lib/chat-storage'
import { RenameModal } from './rename-modal'

interface ChatSidebarProps {
  currentChatId: string | null
  onSelectChat: (chat: ChatSession) => void
  onNewChat: () => void
  onChatDeleted: (deletedChatId: string) => void
  isOpen: boolean
  onToggle: () => void
}

export function ChatSidebar({ currentChatId, onSelectChat, onNewChat, onChatDeleted, isOpen, onToggle }: ChatSidebarProps) {
  const [chats, setChats] = useState<ChatSession[]>([])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [renameModalChat, setRenameModalChat] = useState<ChatSession | null>(null)

  useEffect(() => {
    loadChats()
  }, [currentChatId])

  const loadChats = async () => {
    const allChats = await getAllChats()
    setChats(allChats)
  }

  const startDeleting = (e: React.MouseEvent, chatId: string) => {
    e.stopPropagation()
    setDeletingId(chatId)
  }

  const confirmDelete = async (chatId: string) => {
    await deleteChat(chatId)
    setDeletingId(null)
    loadChats()
    onChatDeleted(chatId)
  }

  const cancelDelete = () => {
    setDeletingId(null)
  }

  const startEditing = (e: React.MouseEvent, chat: ChatSession) => {
    e.stopPropagation()
    setRenameModalChat(chat)
  }

  const handleRenameSubmit = async (newTitle: string) => {
    if (renameModalChat) {
      await updateChatTitle(renameModalChat.id, newTitle)
      setRenameModalChat(null)
      loadChats()
    }
  }

  const handleRenamer = async () => {
    if (renameModalChat) {
      // Make chat eligible for renamer and trigger it
      await triggerRenamer(renameModalChat.id)
      setRenameModalChat(null)
      // Reload after a short delay to allow renamer to process
      setTimeout(() => loadChats(), 1000)
    }
  }

  const closeRenameModal = () => {
    setRenameModalChat(null)
  }

  const saveEdit = async () => {
    if (editingId && editTitle.trim()) {
      await updateChatTitle(editingId, editTitle.trim())
      loadChats()
    }
    setEditingId(null)
    setEditTitle('')
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditTitle('')
  }

  return (
    <>
      {/* Mobile Toggle Button */}
      <button
        onClick={onToggle}
        aria-label="Toggle Sidebar"
        className={cn(
          "fixed left-4 top-3 z-[60] p-2 rounded-lg bg-background border border-border shadow-md hover:bg-muted transition-colors lg:hidden",
          isOpen && "hidden"
        )}
      >
        <Menu className="w-5 h-5" />
      </button>

      {/* Overlay for mobile - opaque background */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <div className={cn(
        "fixed left-0 top-0 h-full bg-background border-r border-border flex flex-col transition-transform duration-200 ease-in-out",
        isOpen ? "translate-x-0 w-full sm:w-80 z-[60]" : "-translate-x-full z-50",
        "lg:translate-x-0 lg:static lg:w-64 lg:min-w-[220px] lg:max-w-[300px]"
      )}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-primary">
              <MessageSquare className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-semibold">Chats</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                console.log('[ChatSidebar] New Chat button clicked, calling onNewChat')
                onNewChat()
              }}
              aria-label="New Chat"
              className="p-1.5 rounded hover:bg-muted transition-colors"
              title="New Chat"
            >
              <Plus className="w-4 h-4" />
            </button>
            <button
              onClick={onToggle}
              aria-label="Close Sidebar"
              className="p-1.5 rounded hover:bg-muted transition-colors lg:hidden"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Chat List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {chats.length === 0 ? (
            <div className="text-center text-muted-foreground text-sm py-8">
              No chats yet
            </div>
          ) : (
            chats.map((chat) => (
              <div
                key={chat.id}
                onClick={() => onSelectChat(chat)}
                className={cn(
                  "group flex items-center gap-2 p-3 rounded-lg cursor-pointer transition-colors",
                  currentChatId === chat.id
                    ? "bg-primary/10 border border-primary/20"
                    : "hover:bg-muted border border-transparent"
                )}
              >
                <MessageSquare className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                
                {editingId === chat.id ? (
                  <div className="flex-1 flex items-center gap-1">
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveEdit()
                        if (e.key === 'Escape') cancelEdit()
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="flex-1 min-w-0 px-2 py-1 text-sm bg-background border border-input rounded focus:outline-none focus:ring-1 focus:ring-ring"
                      autoFocus
                    />
                    <button
                      onClick={(e) => { e.stopPropagation(); saveEdit(); }}
                      aria-label="Save Title"
                      className="p-1 rounded hover:bg-muted"
                    >
                      <Check className="w-3 h-3 text-green-500" />
                    </button>
                  </div>
                ) : deletingId === chat.id ? (
                  <>
                    <span className="flex-1 min-w-0 text-sm truncate text-muted-foreground">
                      Delete "{chat.title}"?
                    </span>
                    <div className="flex items-center gap-0.5">
                      <button
                        onClick={(e) => { e.stopPropagation(); confirmDelete(chat.id); }}
                        aria-label="Confirm Delete"
                        className="p-1 rounded hover:bg-muted"
                        title="Confirm delete"
                      >
                        <Check className="w-3 h-3 text-destructive" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); cancelDelete(); }}
                        aria-label="Cancel Delete"
                        className="p-1 rounded hover:bg-muted"
                        title="Cancel"
                      >
                        <X className="w-3 h-3 text-muted-foreground" />
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <span className="flex-1 min-w-0 text-sm truncate">
                      {chat.title}
                    </span>
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => startEditing(e, chat)}
                        aria-label="Edit Chat"
                        className="p-1 rounded hover:bg-muted"
                      >
                        <Edit2 className="w-3 h-3 text-muted-foreground" />
                      </button>
                      <button
                        onClick={(e) => startDeleting(e, chat.id)}
                        aria-label="Delete Chat"
                        className="p-1 rounded hover:bg-muted"
                      >
                        <Trash2 className="w-3 h-3 text-destructive" />
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-border text-xs text-muted-foreground text-center">
          {chats.length} chat{chats.length !== 1 ? 's' : ''}
        </div>
      </div>

      {/* Rename Modal */}
      <RenameModal
        isOpen={renameModalChat !== null}
        chatId={renameModalChat?.id || ''}
        currentTitle={renameModalChat?.title || ''}
        onClose={closeRenameModal}
        onSubmit={handleRenameSubmit}
        onRenamer={handleRenamer}
      />
    </>
  )
}
