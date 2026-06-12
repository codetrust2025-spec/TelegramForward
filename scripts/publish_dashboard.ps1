#!/usr/bin/env pwsh
<#
  Git-first dashboard publish: build → remind/commit → gate → deploy.
  Does not auto-commit (you commit explicitly before running with -Deploy).
#>
param(
    [switch]$Deploy,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent

if (-not $SkipBuild) {
    Write-Host "Building dashboard..."
    Push-Location (Join-Path $root 'dashboard')
    npm run build
    Pop-Location
}

$dirty = git -C $root status --porcelain
if ($dirty) {
    Write-Host ""
    Write-Host "Git has uncommitted changes (including static/ after build)." -ForegroundColor Yellow
    Write-Host "Commit and push before deploy:" -ForegroundColor Yellow
    Write-Host "  cd $root"
    Write-Host "  git add -A"
    Write-Host "  git commit -m `"your message`""
    Write-Host "  git push origin main"
    Write-Host ""
    if ($Deploy) {
        throw "Refusing to deploy with uncommitted changes (git first, prod second)."
    }
    exit 0
}

python (Join-Path $PSScriptRoot 'git_deploy_gate.py') --require
if (-not $Deploy) {
    Write-Host "Git ready. Re-run with -Deploy to upload static to VPS."
    exit 0
}

if (-not $env:VPS_PASSWORD) {
    throw "Set VPS_PASSWORD before deploy."
}
python (Join-Path $PSScriptRoot 'vps_deploy_dashboard_static.py')
