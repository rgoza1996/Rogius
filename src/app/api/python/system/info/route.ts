/**
 * Next.js API Route - System Info Proxy to Python Backend
 */
import { NextRequest, NextResponse } from 'next/server'

const PYTHON_API_URL = process.env.PYTHON_API_URL || 'http://127.0.0.1:8000'

export async function GET() {
  try {
    const response = await fetch(`${PYTHON_API_URL}/system/info`)
    
    if (!response.ok) {
      return NextResponse.json(
        { error: 'Failed to fetch system info' },
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
