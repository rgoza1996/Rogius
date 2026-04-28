/**
 * Next.js API Route - Chat Storage Info Proxy
 */
import { NextResponse } from 'next/server'

const PYTHON_API_URL = process.env.PYTHON_API_URL || 'http://127.0.0.1:8000'

export async function GET() {
  try {
    const response = await fetch(`${PYTHON_API_URL}/chats/storage/info`)
    
    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to get storage info' },
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
