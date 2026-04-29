#!/usr/bin/env pwsh
# Stop Rogius Python API Server

$ErrorActionPreference = "Stop"

$API_DIR = Join-Path (Join-Path (Join-Path $PSScriptRoot "..") "src") "tui"
$PID_FILE = Join-Path $API_DIR ".api_server.pid"

if (-not (Test-Path $PID_FILE)) {
    Write-Host "No PID file found. Server may not be running." -ForegroundColor Yellow
    
    # Try to find and kill any uvicorn processes
    $uvicornProcesses = Get-Process -Name "python" -ErrorAction SilentlyContinue | 
        Where-Object { $_.CommandLine -like "*uvicorn*api_server*" }
    
    if ($uvicornProcesses) {
        Write-Host "Found uvicorn processes, stopping them..." -ForegroundColor Yellow
        $uvicornProcesses | Stop-Process -Force
        Write-Host "Stopped $($uvicornProcesses.Count) process(es)" -ForegroundColor Green
    }
    
    exit 0
}

$pid_content = Get-Content $PID_FILE -ErrorAction SilentlyContinue

if (-not $pid_content) {
    Write-Host "PID file is empty" -ForegroundColor Yellow
    Remove-Item $PID_FILE -ErrorAction SilentlyContinue
    exit 0
}

try {
    $processId = [int]$pid_content
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    
    if ($process) {
        Write-Host "Stopping Python API server (PID: $processId)..." -ForegroundColor Yellow
        Stop-Process -Id $processId -Force
        Write-Host "Server stopped" -ForegroundColor Green
    } else {
        Write-Host "Process not found (may have already exited)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Error stopping process: $_" -ForegroundColor Red
}

# Clean up PID file
Remove-Item $PID_FILE -ErrorAction SilentlyContinue
Write-Host "Cleanup complete" -ForegroundColor Green
