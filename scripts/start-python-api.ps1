#!/usr/bin/env pwsh
# Start Rogius Python API Server

$ErrorActionPreference = "Stop"

$API_DIR = Join-Path (Join-Path (Join-Path $PSScriptRoot "..") "src") "tui"
$PID_FILE = Join-Path $API_DIR ".api_server.pid"

# Check if already running
if (Test-Path $PID_FILE) {
    $pid_content = Get-Content $PID_FILE -ErrorAction SilentlyContinue
    if ($pid_content) {
        try {
            $process = Get-Process -Id $pid_content -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "Python API server already running (PID: $pid_content)" -ForegroundColor Yellow
                Write-Host "Visit: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
                exit 0
            }
        } catch {}
    }
}

Write-Host "Starting Rogius Python API Server..." -ForegroundColor Green
Write-Host "Working directory: $API_DIR" -ForegroundColor Gray

# Start the server
$process = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "api_server:app", "--host", "127.0.0.1", "--port", "8000", "--reload" `
    -WorkingDirectory $API_DIR `
    -WindowStyle Hidden `
    -PassThru

# Save PID
$process.Id | Out-File $PID_FILE

Write-Host "API server started with PID: $($process.Id)" -ForegroundColor Green
Write-Host "Health check: http://127.0.0.1:8000/health" -ForegroundColor Cyan
Write-Host "API docs:     http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "To stop: Run scripts\stop-python-api.ps1" -ForegroundColor Yellow
