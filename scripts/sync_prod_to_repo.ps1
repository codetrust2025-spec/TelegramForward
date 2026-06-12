#!/usr/bin/env pwsh
<#
.SYNOPSIS
  Sync production work from Desktop\Automation into this git repo before commit.

.DESCRIPTION
  Canonical repo: TelegramForward (this folder).
  Remote: https://github.com/codetrust2025-spec/TelegramForward.git
  Branch: main

  GIT FIRST, PROD SECOND — never deploy before commit + push.
  Deploy scripts call git_deploy_gate.py and will refuse if git is dirty or unpushed.
    pwsh scripts/sync_prod_to_repo.ps1
    git status
    git add -A && git commit -m "your message" && git push origin main

  Requires OneDrive files to be available offline (hydrated) — open the Automation
  folder in Explorer first if copy fails with "cloud file provider is not running".
#>
$ErrorActionPreference = 'Stop'
$srcRoot = Join-Path $env:USERPROFILE 'OneDrive\Desktop\Automation'
$dstRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path (Join-Path $dstRoot '.git'))) {
  $dstRoot = Split-Path $PSScriptRoot -Parent
}
if (-not (Test-Path (Join-Path $dstRoot '.git'))) {
  throw "Run from TelegramForward repo (could not find .git)"
}

$pairs = @(
  @{ Src = 'dashboard'; Dst = 'dashboard'; Exclude = @('node_modules', 'dist', '.git') },
  @{ Src = 'static'; Dst = 'static'; Exclude = @() },
  @{ Src = 'scripts'; Dst = 'scripts'; Exclude = @() }
)

foreach ($pair in $pairs) {
  $from = Join-Path $srcRoot $pair.Src
  $to = Join-Path $dstRoot $pair.Dst
  if (-not (Test-Path $from)) {
    Write-Warning "Skip missing source: $from"
    continue
  }
  Write-Host "Sync $($pair.Src) -> $($pair.Dst)"
  $args = @($from, $to, '/E', '/R:2', '/W:2', '/NFL', '/NDL', '/NJH', '/NJS')
  foreach ($xd in $pair.Exclude) { $args += '/XD'; $args += $xd }
  & robocopy @args | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $($pair.Src) (exit $LASTEXITCODE)" }
}

# Strip hardcoded VPS password fallbacks from copied scripts
Get-ChildItem (Join-Path $dstRoot 'scripts') -Filter '*.py' -File | ForEach-Object {
  $text = Get-Content $_.FullName -Raw -Encoding UTF8
  $new = [regex]::Replace($text, 'os\.environ\.get\("VPS_PASSWORD",\s*"[^"]*"\)', 'os.environ.get("VPS_PASSWORD", "")')
  if ($new -ne $text) { Set-Content $_.FullName -Value $new -Encoding UTF8 -NoNewline }
}

Write-Host "Done. Review with: git -C `"$dstRoot`" status"
