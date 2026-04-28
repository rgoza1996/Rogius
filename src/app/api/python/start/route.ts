/**
 * Next.js API Route - Start Python Backend Server
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
    const scriptPath = path.join(projectRoot, 'scripts', 'start-python-api.ps1')

    // Execute the PowerShell script to start the Python API
    // Using powershell with Bypass execution policy
    const { stdout, stderr } = await execAsync(
      `powershell -ExecutionPolicy Bypass -File "${scriptPath}"`,
      { timeout: 10000 }
    )

    if (stderr && !stderr.includes('already running')) {
      console.warn('Python API start stderr:', stderr)
    }

    return NextResponse.json({
      status: 'started',
      message: stdout.trim() || 'Python API server started'
    })
  } catch (error) {
    // Check if it's already running
    const errorStr = String(error)
    if (errorStr.includes('already running')) {
      return NextResponse.json({
        status: 'already_running',
        message: 'Python API server is already running'
      })
    }

    console.error('Failed to start Python API:', error)
    return NextResponse.json(
      {
        status: 'error',
        error: 'Failed to start Python API server',
        details: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    )
  }
}
