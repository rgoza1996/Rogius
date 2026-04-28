/**
 * Next.js API Route - Multi-Step Proxy to Python Backend
 */
import { NextRequest, NextResponse } from 'next/server'

const PYTHON_API_URL = process.env.PYTHON_API_URL || 'http://127.0.0.1:8000'

export async function POST(request: NextRequest) {
  try {
    const { action, ...data } = await request.json()
    
    let endpoint = '/multistep/create'
    
    switch (action) {
      case 'create':
        endpoint = '/multistep/create'
        break
      case 'execute':
        endpoint = '/multistep/execute'
        break
      case 'execute-next':
        endpoint = '/multistep/execute-next'
        break
      case 'clear':
        endpoint = '/multistep/clear'
        break
      default:
        return NextResponse.json(
          { error: 'Invalid action' },
          { status: 400 }
        )
    }
    
    const response = await fetch(`${PYTHON_API_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    
    if (!response.ok) {
      const error = await response.json()
      return NextResponse.json(
        { error: error.detail || 'Python backend error' },
        { status: response.status }
      )
    }
    
    const result = await response.json()
    return NextResponse.json(result)
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to connect to Python backend', details: String(error) },
      { status: 500 }
    )
  }
}

export async function GET() {
  try {
    const response = await fetch(`${PYTHON_API_URL}/multistep/status`)
    
    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch status' },
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
