# TeleAutomation - Start Ollama + Reverse SSH Tunnel
# Run this script in PowerShell AFTER installing Ollama from https://ollama.com/download/windows
# This laptop must have 64 GB RAM and Ollama installed.
# Do NOT run this on VPS.

Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  TeleAutomation - Ollama AI Setup" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Ollama is installed
Write-Host "[1/5] Checking Ollama installation..." -ForegroundColor Yellow
$ollamaPath = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollamaPath) {
    Write-Host "  ERROR: Ollama not found!" -ForegroundColor Red
    Write-Host "  Install from: https://ollama.com/download/windows" -ForegroundColor Red
    Write-Host "  After install, CLOSE this window and open a new PowerShell." -ForegroundColor Red
    exit 1
}
$version = & ollama --version 2>&1
Write-Host "  OK: $version" -ForegroundColor Green

# Step 2: Check if Ollama is running
Write-Host "[2/5] Checking Ollama service..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "  OK: Ollama is running" -ForegroundColor Green
} catch {
    Write-Host "  Starting Ollama..." -ForegroundColor Yellow
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
        Write-Host "  OK: Ollama started" -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: Cannot start Ollama" -ForegroundColor Red
        exit 1
    }
}

# Step 3: Check/pull vision model
Write-Host "[3/5] Checking qwen2.5vl:7b model..." -ForegroundColor Yellow
$models = & ollama list 2>&1
if ($models -match "qwen2.5vl") {
    Write-Host "  OK: qwen2.5vl:7b already available" -ForegroundColor Green
} else {
    Write-Host "  Pulling qwen2.5vl:7b (this may take 5-10 minutes)..." -ForegroundColor Yellow
    & ollama pull qwen2.5vl:7b
    Write-Host "  OK: Model pulled" -ForegroundColor Green
}

# Step 4: Show local model list
Write-Host "[4/5] Local models:" -ForegroundColor Yellow
& ollama list

# Step 5: Start reverse SSH tunnel
Write-Host ""
Write-Host "[5/5] Starting reverse SSH tunnel to VPS..." -ForegroundColor Yellow
Write-Host "  This connects your laptop Ollama to the VPS." -ForegroundColor Gray
Write-Host "  Keep this window open while using AI extraction." -ForegroundColor Gray
Write-Host "  Press Ctrl+C to stop the tunnel." -ForegroundColor Gray
Write-Host ""
Write-Host "  Connecting to 187.127.169.159..." -ForegroundColor Cyan
Write-Host "  Enter VPS password when prompted." -ForegroundColor Cyan
Write-Host ""

# Start SSH tunnel (will ask for password)
ssh -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=60 -R 127.0.0.1:11434:127.0.0.1:11434 root@187.127.169.159
