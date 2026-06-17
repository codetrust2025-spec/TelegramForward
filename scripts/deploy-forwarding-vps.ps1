# Deploy forwarding mode to Hostinger VPS (interactive password).
# Run from repo root:  powershell -ExecutionPolicy Bypass -File scripts/deploy-forwarding-vps.ps1

$VpsHost = "187.127.169.159"
$VpsUser = "root"
$RemotePath = "/opt/telegramforward"

Write-Host "=== TelegramForward VPS deploy ===" -ForegroundColor Cyan
Write-Host "Host: ${VpsUser}@${VpsHost}"
Write-Host "Remote: $RemotePath"
Write-Host ""
Write-Host "You will be prompted for the VPS password (twice per step if needed)."
Write-Host ""

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot

# Trust host key on first connect
ssh -o StrictHostKeyChecking=accept-new "${VpsUser}@${VpsHost}" "echo SSH OK"

if ($LASTEXITCODE -ne 0) {
    Write-Host "SSH failed. Fix connectivity or credentials and retry." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[1/3] Syncing files (rsync via scp batch)..." -ForegroundColor Yellow

$files = @(
    "core/posting_mode.py",
    "features/interval_forward.py",
    "workers/account_worker.py",
    "workers/account_state.py",
    "server.py",
    "services/account_manager.py",
    "dashboard/src/App.jsx",
    "dashboard/src/index.css",
    "dashboard/src/components/AccountCard.jsx",
    "dashboard/src/components/AccountPanel.jsx",
    "dashboard/src/components/PostingModePanel.jsx"
)

foreach ($f in $files) {
    $remoteDir = "$RemotePath/" + (Split-Path $f -Parent).Replace("\", "/")
    ssh "${VpsUser}@${VpsHost}" "mkdir -p `"$remoteDir`""
    scp -o StrictHostKeyChecking=accept-new $f "${VpsUser}@${VpsHost}:${RemotePath}/$($f.Replace('\','/'))"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed uploading $f" -ForegroundColor Red
        exit 1
    }
    Write-Host "  uploaded $f"
}

Write-Host ""
Write-Host "[2/3] Building dashboard on VPS..." -ForegroundColor Yellow
ssh "${VpsUser}@${VpsHost}" "cd $RemotePath/dashboard && npm run build"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Dashboard build failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[3/3] Production restart..." -ForegroundColor Yellow
ssh "${VpsUser}@${VpsHost}" "cd $RemotePath && bash scripts/production_update.sh"

Write-Host ""
Write-Host "Done. Open https://teleautomation.online and set Forwarding mode per account." -ForegroundColor Green
