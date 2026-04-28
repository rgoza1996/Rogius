/**
 * Next.js API Route - Renamer Agent Proxy to Python Backend
 * 
 * Forwards renamer requests to the Python FastAPI server.
 */
import { NextRequest, NextResponse } from 'next/server'

const PYTHON_API_URL = process.env.PYTHON_API_URL || 'http://127.0.0.1:8000'

// GET /api/python/renamer - Get renamer status
export async function GET(request: NextRequest) {
  try {
    const url = new URL(request.url)
    const path = url.pathname.split('/').pop()
    
    // Handle /renamer/status
    if (path === 'status' || !path) {
      const response = await fetch(`${PYTHON_API_URL}/renamer/status`)
      if (!response.ok) {
        return NextResponse.json(
          { error: 'Failed to get renamer status' },
          { status: response.status }
        )
      }
      const data = await response.json()
      return NextResponse.json(data)
    }
    
    // Handle /renamer/queue
    if (path === 'queue') {
      const response = await fetch(`${PYTHON_API_URL}/renamer/queue`)
      if (!response.ok) {
        return NextResponse.json(
          { error: 'Failed to get queue' },
          { status: response.status }
        )
      }
      const data = await response.json()
      return NextResponse.json(data)
    }
    
    return NextResponse.json({ error: 'Unknown endpoint' }, { status: 404 })
  } catch (error) {
    console.error('[API /renamer] GET Error:', error)
    return NextResponse.json(
      { error: 'Failed to connect to Python backend', details: String(error) },
      { status: 500 }
    )
  }
}

// POST /api/python/renamer - Forward POST requests
export async function POST(request: NextRequest) {
  try {
    const url = new URL(request.url)
    const pathSegments = url.pathname.split('/')
    const action = pathSegments[pathSegments.length - 1] // enqueue, dequeue, toggle-eligibility, process
    
    const body = await request.json()
    
    let endpoint = ''
    switch (action) {
      case 'enqueue':
        endpoint = '/renamer/enqueue'
        break
      case 'dequeue':
        endpoint = '/renamer/dequeue'
        break
      case 'toggle-eligibility':
        endpoint = '/renamer/toggle-eligibility'
        break
      case 'process':
        endpoint = '/renamer/process'
        break
      default:
        // If no specific action, try to determine from body or use status
        if (body.chat_id && 'eligible' in body) {
          endpoint = '/renamer/toggle-eligibility'
        } else if (body.chat_id) {
          endpoint = '/renamer/enqueue'
        } else {
          return NextResponse.json({ error: 'Unknown action' }, { status: 400 })
        }
    }
    
    console.log(`[API /renamer] Forwarding to ${endpoint}`, body)
    
    const response = await fetch(`${PYTHON_API_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      console.error('[API /renamer] Python backend error:', response.status, errorText)
      return NextResponse.json(
        { error: errorText || 'Renamer request failed' },
        { status: response.status }
      )
    }
    
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error('[API /renamer] POST Error:', error)
    return NextResponse.json(
      { error: 'Failed to connect to Python backend', details: String(error) },
      { status: 500 }
    )
  }
}
