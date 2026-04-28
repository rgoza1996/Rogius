import { NextRequest, NextResponse } from 'next/server'
import { spawn } from 'child_process'
import { join } from 'path'

const PROJECT_ROOT = process.cwd()

export async function POST(request: NextRequest) {
  try {
    const { command, cwd } = await request.json()
    
    if (!command || typeof command !== 'string') {
      return NextResponse.json(
        { error: 'Command is required' },
        { status: 400 }
      )
    }
    
    // Resolve working directory
    const workingDir = cwd ? join(PROJECT_ROOT, cwd) : PROJECT_ROOT
    
    // Always use PowerShell for better capabilities
    const shell = 'powershell.exe'
    const shellArgs = ['-Command', command]
    
    return new Promise<NextResponse>((resolve) => {
      const child = spawn(shell, shellArgs, {
        cwd: workingDir,
        env: { ...process.env, FORCE_COLOR: '1' }
      })
      
      let stdout = ''
      let stderr = ''
      
      child.stdout.on('data', (data) => {
        stdout += data.toString()
      })
      
      child.stderr.on('data', (data) => {
        stderr += data.toString()
      })
      
      child.on('close', (exitCode) => {
        resolve(NextResponse.json({
          stdout: stdout.trim(),
          stderr: stderr.trim(),
          exitCode: exitCode ?? 0,
          cwd: workingDir.replace(PROJECT_ROOT, '').replace(/^\\/, '') || '.'
        }))
      })
      
      child.on('error', (error) => {
        resolve(NextResponse.json({
          stdout: '',
          stderr: error.message,
          exitCode: 1,
          cwd: workingDir.replace(PROJECT_ROOT, '').replace(/^\\/, '') || '.'
        }))
      })
      
      // Timeout after 30 seconds
      setTimeout(() => {
        child.kill()
        resolve(NextResponse.json({
          stdout: stdout.trim(),
          stderr: (stderr + '\nCommand timed out after 30 seconds').trim(),
          exitCode: 124,
          cwd: workingDir.replace(PROJECT_ROOT, '').replace(/^\\/, '') || '.'
        }))
      }, 30000)
    })
    
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to execute command', details: String(error) },
      { status: 500 }
    )
  }
}
