# Reproduce the Scheduled Task environment: LOCALAPPDATA absent.
# Extracts Resolve-LogDirectory from the real script so the test tracks the source.

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$scriptPath = Join-Path $repoRoot "scripts\ollama_tunnel_keepalive.ps1"
$src = Get-Content -LiteralPath $scriptPath -Raw

$start = $src.IndexOf("function Resolve-LogDirectory")
$end = $src.IndexOf("`$LogDir = Resolve-LogDirectory")
if ($start -lt 0 -or $end -lt 0) { throw "Could not extract Resolve-LogDirectory" }
Invoke-Expression $src.Substring($start, $end - $start)

$saveLocal = $env:LOCALAPPDATA
$saveProfile = $env:USERPROFILE
$results = @()

try {
    # 1. Normal: LOCALAPPDATA present
    $env:LOCALAPPDATA = $saveLocal
    $d = Resolve-LogDirectory
    $results += [pscustomobject]@{ Case = "LOCALAPPDATA present"; Path = $d; Rooted = [System.IO.Path]::IsPathRooted($d) }

    # 2. The actual bug: LOCALAPPDATA missing, USERPROFILE present
    $env:LOCALAPPDATA = ""
    $d = Resolve-LogDirectory
    $results += [pscustomobject]@{ Case = "LOCALAPPDATA MISSING"; Path = $d; Rooted = [System.IO.Path]::IsPathRooted($d) }

    # 3. Both gone -> TEMP
    $env:USERPROFILE = ""
    $d = Resolve-LogDirectory
    $results += [pscustomobject]@{ Case = "LOCALAPPDATA+USERPROFILE gone"; Path = $d; Rooted = [System.IO.Path]::IsPathRooted($d) }
}
finally {
    $env:LOCALAPPDATA = $saveLocal
    $env:USERPROFILE = $saveProfile
}

$results | Format-Table -AutoSize

$bad = $results | Where-Object { -not $_.Rooted }
if ($bad) { "FAIL: unrooted path returned"; exit 1 }

# Prove the old expression really was broken, so the test documents the defect.
$env:LOCALAPPDATA = ""
$old = Join-Path $env:LOCALAPPDATA "TeleAutomation\logs"
$env:LOCALAPPDATA = $saveLocal
"old expression with LOCALAPPDATA empty -> '$old'  rooted=$([System.IO.Path]::IsPathRooted($old))"
if ([System.IO.Path]::IsPathRooted($old)) { "UNEXPECTED: old form was rooted"; exit 1 }

"PASS: every case returns a rooted path; the old form did not"
