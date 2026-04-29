#!/usr/bin/env powershell
# KokoroTTS Server Manager
# Manages the KokoroTTS server on roggoz via SSH through tailscale

param(
    [switch]$Status,
    [switch]$Start,
    [switch]$Stop,
    [switch]$Logs,
    [switch]$InstallService
)

$ROGGOZ_IP = "100.71.89.62"
$ROGGOZ_USER = "roggoz"
$KOKORO_PORT = 8880

function Test-KokoroServer {
    try {
        $response = Invoke-WebRequest -Uri "http://${ROGGOZ_IP}:${KOKORO_PORT}/v1/audio/speech" -Method OPTIONS -TimeoutSec 5 -ErrorAction SilentlyContinue
        return $true
    } catch {
        return $false
    }
}

function Start-KokoroServer {
    Write-Host "Starting KokoroTTS server on roggoz..." -ForegroundColor Yellow
    Write-Host "Note: First startup may take 2-3 minutes for model loading on CPU" -ForegroundColor Yellow
    Write-Host ""
    
    # Start in a screen session so it persists
    $sshCmd = @"
cd ~ && screen -dmS kokoro bash -c 'python3 kokoro-server.py; exec bash'
"@
    
    ssh "${ROGGOZ_USER}@${ROGGOZ_IP}" $sshCmd
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "KokoroTTS server starting in screen session 'kokoro'" -ForegroundColor Green
        Write-Host "Waiting for server to be ready..." -ForegroundColor Yellow
        
        # Wait for server to be ready
        $attempts = 0
        $maxAttempts = 30
        while ($attempts -lt $maxAttempts) {
            Start-Sleep -Seconds 5
            $attempts++
            
            if (Test-KokoroServer) {
                Write-Host "KokoroTTS server is ready!" -ForegroundColor Green
                return
            }
            
            Write-Host "Waiting... ($attempts/$maxAttempts)" -ForegroundColor Gray
        }
        
        Write-Host "Server may still be loading (takes 2-3 min on first start)" -ForegroundColor Yellow
        Write-Host "Check logs with: ssh ${ROGGOZ_USER}@${ROGGOZ_IP} 'screen -r kokoro'" -ForegroundColor Cyan
    } else {
        Write-Error "Failed to start KokoroTTS server"
    }
}

function Stop-KokoroServer {
    Write-Host "Stopping KokoroTTS server on roggoz..." -ForegroundColor Yellow
    ssh "${ROGGOZ_USER}@${ROGGOZ_IP}" "pkill -f kokoro-server.py || screen -S kokoro -X quit"
    Write-Host "KokoroTTS server stopped" -ForegroundColor Green
}

function Show-KokoroLogs {
    Write-Host "Connecting to KokoroTTS logs..." -ForegroundColor Yellow
    Write-Host "Press Ctrl+A then D to detach from screen" -ForegroundColor Cyan
    Start-Sleep -Seconds 2
    ssh -t "${ROGGOZ_USER}@${ROGGOZ_IP}" "screen -r kokoro"
}

function Install-KokoroService {
    Write-Host "Installing KokoroTTS as systemd service on roggoz..." -ForegroundColor Yellow
    
    $serviceFile = @"
[Unit]
Description=Kokoro TTS Server
After=network.target

[Service]
Type=simple
User=roggoz
WorkingDirectory=/home/roggoz
ExecStart=/usr/bin/python3 /home/roggoz/kokoro-server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"@
    
    # Write service file
    $serviceFile | ssh "${ROGGOZ_USER}@${ROGGOZ_IP}" "sudo tee /etc/systemd/system/kokoro-tts.service"
    
    # Reload and enable
    ssh "${ROGGOZ_USER}@${ROGGOZ_IP}" "sudo systemctl daemon-reload && sudo systemctl enable kokoro-tts"
    
    Write-Host "Service installed. Start with: ssh ${ROGGOZ_USER}@${ROGGOZ_IP} 'sudo systemctl start kokoro-tts'" -ForegroundColor Green
}

# Main script logic
if ($Status) {
    if (Test-KokoroServer) {
        Write-Host "KokoroTTS server is RUNNING on ${ROGGOZ_IP}:${KOKORO_PORT}" -ForegroundColor Green
    } else {
        Write-Host "KokoroTTS server is NOT RUNNING on ${ROGGOZ_IP}:${KOKORO_PORT}" -ForegroundColor Red
        Write-Host "Start it with: .\start-kokoro-server.ps1 -Start" -ForegroundColor Yellow
    }
}
elseif ($Start) {
    Start-KokoroServer
}
elseif ($Stop) {
    Stop-KokoroServer
}
elseif ($Logs) {
    Show-KokoroLogs
}
elseif ($InstallService) {
    Install-KokoroService
}
else {
    Write-Host "KokoroTTS Server Manager" -ForegroundColor Cyan
    Write-Host "=======================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\start-kokoro-server.ps1 -Status          # Check if server is running"
    Write-Host "  .\start-kokoro-server.ps1 -Start           # Start the server"
    Write-Host "  .\start-kokoro-server.ps1 -Stop            # Stop the server"
    Write-Host "  .\start-kokoro-server.ps1 -Logs            # View server logs"
    Write-Host "  .\start-kokoro-server.ps1 -InstallService  # Install as systemd service"
    Write-Host ""
    
    # Default to status check
    if (Test-KokoroServer) {
        Write-Host "KokoroTTS server is RUNNING" -ForegroundColor Green
    } else {
        Write-Host "KokoroTTS server is NOT RUNNING" -ForegroundColor Red
    }
}
