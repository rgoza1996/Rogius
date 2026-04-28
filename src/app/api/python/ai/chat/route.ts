/**
 * Next.js API Route - AI Chat Proxy to Python Backend
 * 
 * Supports both regular and streaming chat completions.
 */
import { NextRequest, NextResponse } from 'next/server'

const PYTHON_API_URL = process.env.PYTHON_API_URL || 'http://127.0.0.1:8000'

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { stream = false, ...rest } = body
    
    if (stream) {
      // Streaming response - proxy the stream
      const response = await fetch(`${PYTHON_API_URL}/ai/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rest),
      })
      
      if (!response.ok) {
        const error = await response.json()
        return NextResponse.json(
          { error: error.detail || 'Python backend error' },
          { status: response.status }
        )
      }
      
      // Return the stream directly
      return new NextResponse(response.body, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      })
    }
    
    // Non-streaming
    const response = await fetch(`${PYTHON_API_URL}/ai/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    
    if (!response.ok) {
      const error = await response.json()
      return NextResponse.json(
        { error: error.detail || 'Python backend error' },
        { status: response.status }
      )
    }
    
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to connect to Python backend', details: String(error) },
      { status: 500 }
    )
  }
}

// Get available models
export async function GET() {
  try {
    const response = await fetch(`${PYTHON_API_URL}/ai/models`)
    
    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch models' },
        { status: response.status }
      )
    }
    
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to connect to Python backend', details: String(error) },
      { status: 500 }
    )
  }
}
