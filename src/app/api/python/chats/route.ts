/**
 * Next.js API Route - Chat Storage Proxy to Python Backend
 * 
 * Forwards chat storage requests to the Python FastAPI server.
 * This enables shared storage across all ports (3000, 3001, etc.)
 */
import { NextRequest, NextResponse } from 'next/server'

const PYTHON_API_URL = process.env.PYTHON_API_URL || 'http://127.0.0.1:8000'

// GET /api/python/chats - List all chats
export async function GET(request: NextRequest) {
  try {
    const url = new URL(request.url)
    const chatId = url.searchParams.get('id')
    
    if (chatId) {
      // Get specific chat
      const response = await fetch(`${PYTHON_API_URL}/chats/${chatId}`)
      if (!response.ok) {
        return NextResponse.json(
          { error: 'Chat not found' },
          { status: response.status }
        )
      }
      const data = await response.json()
      return NextResponse.json(data)
    } else {
      // List all chats
      const response = await fetch(`${PYTHON_API_URL}/chats`)
      if (!response.ok) {
        return NextResponse.json(
          { error: 'Failed to list chats' },
          { status: response.status }
        )
      }
      const data = await response.json()
      return NextResponse.json(data)
    }
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to connect to Python backend', details: String(error) },
      { status: 500 }
    )
  }
}

// POST /api/python/chats - Save a chat
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    console.log('[API /chats] Saving chat:', body.id, 'with', body.messages?.length, 'messages')
    
    const response = await fetch(`${PYTHON_API_URL}/chats`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error('[API /chats] Python backend error:', response.status, errorText)
      return NextResponse.json(
        { error: errorText || 'Failed to save chat' },
        { status: response.status }
      )
    }
    
    const data = await response.json()
    console.log('[API /chats] Saved successfully:', data)
    return NextResponse.json(data)
  } catch (error) {
    console.error('[API /chats] Error:', error)
    return NextResponse.json(
      { error: 'Failed to connect to Python backend', details: String(error) },
      { status: 500 }
    )
  }
}

// DELETE /api/python/chats - Clear all chats or delete specific chat
export async function DELETE(request: NextRequest) {
  try {
    const url = new URL(request.url)
    const chatId = url.searchParams.get('id')
    
    if (chatId) {
      // Delete specific chat
      const response = await fetch(`${PYTHON_API_URL}/chats/${chatId}`, {
        method: 'DELETE',
      })
      if (!response.ok) {
        const error = await response.json()
        return NextResponse.json(
          { error: error.detail || 'Failed to delete chat' },
          { status: response.status }
        )
      }
      const data = await response.json()
      return NextResponse.json(data)
    } else {
      // Clear all chats
      const response = await fetch(`${PYTHON_API_URL}/chats`, {
        method: 'DELETE',
      })
      if (!response.ok) {
        const error = await response.json()
        return NextResponse.json(
          { error: error.detail || 'Failed to clear chats' },
          { status: response.status }
        )
      }
      const data = await response.json()
      return NextResponse.json(data)
    }
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to connect to Python backend', details: String(error) },
      { status: 500 }
    )
  }
}
