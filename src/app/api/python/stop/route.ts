/**
 * Next.js API Route - Stop Python Backend Server
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
    const scriptPath = path.join(projectRoot, 'scripts', 'stop-python-api.ps1')

    // Execute the PowerShell script to stop the Python API
    const { stdout, stderr } = await execAsync(
      `powershell -ExecutionPolicy Bypass -File "${scriptPath}"`,
      { timeout: 10000 }
    )

    if (stderr && !stderr.includes('not running')) {
      console.warn('Python API stop stderr:', stderr)
    }

    return NextResponse.json({
      status: 'stopped',
      message: stdout.trim() || 'Python API server stopped'
    })
  } catch (error) {
    // Check if it's already stopped
    const errorStr = String(error)
    if (errorStr.includes('not running') || errorStr.includes('not found')) {
      return NextResponse.json({
        status: 'already_stopped',
        message: 'Python API server is not running'
      })
    }

    console.error('Failed to stop Python API:', error)
    return NextResponse.json(
      {
        status: 'error',
        error: 'Failed to stop Python API server',
        details: error instanceof Error ? error.message : String(error)
      },
      { status: 500 }
    )
  }
}
