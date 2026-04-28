/**
 * Next.js API Route - Start Kokoro TTS Server on roggoz
 * DEBUG ROUTE - Will be removed after debugging
 */
import { NextResponse } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execAsync = promisify(exec)

export async function POST() {
  try {
    // Get the project root directory
    const projectRoot = process.cwd()
    const scriptPath = path.join(projectRoot, 'scripts', 'start-kokoro-server.ps1')

    // Execute the PowerShell script to start the Kokoro server
    // Using powershell with Bypass execution policy
    const { stdout, stderr } = await execAsync(
      `powershell -ExecutionPolicy Bypass -File "${scriptPath}" -Start`,
      { timeout: 30000 } // 30 second timeout for SSH operations
    )

    if (stderr) {
      console.warn('Kokoro start stderr:', stderr)
    }

    console.log('Kokoro start stdout:', stdout)

    return NextResponse.json({
      status: 'started',
      message: stdout.trim() || 'Kokoro server start command sent. Wait 2-3 minutes for model loading.'
    })
  } catch (error) {
    const errorStr = String(error)
    
    // Check if it's a connection-related error
    if (errorStr.includes('ssh') || errorStr.includes('connection')) {
      console.error('SSH connection error:', error)
      return NextResponse.json(
        {
          status: 'error',
          error: 'SSH connection failed',
          details: 'Could not connect to roggoz. Check tailscale connection.',
          fullError: error instanceof Error ? error.message : String(error)
        },
        { status: 500 }
      )
    }

    console.error('Failed to start Kokoro server:', error)
    return NextResponse.json(
      {
        status: 'error',
        error: 'Failed to start Kokoro server',
        details: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    )
  }
}
