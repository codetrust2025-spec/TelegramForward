# Start SSH tunnel for Ollama from laptop to VPS
# This makes your local Ollama (localhost:11434) available on VPS as localhost:11434

$VPS_HOST = "187.127.169.159"
$VPS_USER = "root"
$VPS_PASSWORD = "REMOVED_VPS_PASSWORD"
$LOCAL_OLLAMA_PORT = 11434
$REMOTE_OLLAMA_PORT = 11434

Write-Host "=== Starting Ollama SSH Tunnel ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "This will tunnel your LOCAL Ollama (localhost:11434)" -ForegroundColor Yellow
Write-Host "to VPS (187.127.169.159) so the VPS can use your laptop's AI." -ForegroundColor Yellow
Write-Host ""

# Check if Ollama is running locally
Write-Host "[1/3] Checking if Ollama is running locally..."
try {
    $response = Invoke-WebRequest -Uri "http://localhost:$LOCAL_OLLAMA_PORT/api/tags" -TimeoutSec 5 -UseBasicParsing
    Write-Host "  ✓ Ollama is running on localhost:$LOCAL_OLLAMA_PORT" -ForegroundColor Green
} catch {
    Write-Host "  ✗ Ollama is NOT running on localhost:$LOCAL_OLLAMA_PORT" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please start Ollama first:" -ForegroundColor Yellow
    Write-Host "  - On Windows: Open Ollama app from Start menu" -ForegroundColor White
    Write-Host "  - Or run: ollama serve" -ForegroundColor White
    exit 1
}

Write-Host ""
Write-Host "[2/3] Checking if tunnel is already active..."
$existingTunnel = Get-Process -Name ssh -ErrorAction SilentlyContinue | Where-Object { 
    $_.CommandLine -like "*$VPS_HOST*" -and $_.CommandLine -like "*$REMOTE_OLLAMA_PORT*" 
}

if ($existingTunnel) {
    Write-Host "  ! SSH tunnel already running (PID: $($existingTunnel.Id))" -ForegroundColor Yellow
    Write-Host "    To restart, kill it first: Stop-Process -Id $($existingTunnel.Id)" -ForegroundColor White
    exit 0
}

Write-Host "  No existing tunnel found" -ForegroundColor White

Write-Host ""
Write-Host "[3/3] Starting SSH tunnel..."
Write-Host "  Command: ssh -R $REMOTE_OLLAMA_PORT:localhost:$LOCAL_OLLAMA_PORT ${VPS_USER}@${VPS_HOST}" -ForegroundColor Gray

# Check if ssh command exists
if (!(Get-Command ssh -ErrorAction SilentlyContinue)) {
    Write-Host "  ✗ SSH command not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install OpenSSH:" -ForegroundColor Yellow
    Write-Host "  Settings > Apps > Optional Features > Add Feature > OpenSSH Client" -ForegroundColor White
    exit 1
}

Write-Host ""
Write-Host "NOTE: This will prompt for password. Type: $VPS_PASSWORD" -ForegroundColor Yellow
Write-Host "      Keep this window open - closing it will stop the tunnel!" -ForegroundColor Yellow
Write-Host ""

# Start tunnel with keepalive
ssh -R ${REMOTE_OLLAMA_PORT}:localhost:${LOCAL_OLLAMA_PORT} `
    -o ServerAliveInterval=60 `
    -o ServerAliveCountMax=3 `
    -o StrictHostKeyChecking=no `
    ${VPS_USER}@${VPS_HOST}
