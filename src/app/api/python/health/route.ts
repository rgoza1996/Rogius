/**
 * Next.js API Route - Python Backend Health Check
 */
import { NextResponse } from 'next/server'

const PYTHON_API_URL = process.env.PYTHON_API_URL || 'http://127.0.0.1:8000'

export async function GET() {
  try {
    // Create an AbortController for timeout
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 3000)
    
    const response = await fetch(`${PYTHON_API_URL}/health`, {
      signal: controller.signal,
    })
    
    clearTimeout(timeoutId)
    
    if (!response.ok) {
      return NextResponse.json(
        { 
          status: 'unhealthy',
          python_backend: 'error',
          message: 'Python backend returned error'
        },
        { status: 503 }
      )
    }
    
    const data = await response.json()
    return NextResponse.json({
      status: 'healthy',
      python_backend: 'connected',
      python_version: data.version,
      python_timestamp: data.timestamp
    })
  } catch (error) {
    return NextResponse.json(
      { 
        status: 'unhealthy',
        python_backend: 'disconnected',
        message: 'Cannot connect to Python backend',
        error: String(error)
      },
      { status: 503 }
    )
  }
}
