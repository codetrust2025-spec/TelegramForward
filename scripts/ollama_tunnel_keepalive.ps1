$ErrorActionPreference = "Continue"

$VpsHost = "187.127.169.159"
$VpsUser = "root"
$SshKey = Join-Path $env:USERPROFILE ".ssh\teleautomation_vps_ed25519"
$LogDir = Join-Path $env:LOCALAPPDATA "TeleAutomation\logs"
$LogFile = Join-Path $LogDir "ollama-tunnel.log"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Write-TunnelLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $LogFile -Value "[$timestamp] $Message"
}

if (-not (Test-Path -LiteralPath $SshKey)) {
    Write-TunnelLog "Dedicated SSH key not found: $SshKey"
    exit 1
}

while ($true) {
    try {
        $ollamaReady = Invoke-WebRequest -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5 -UseBasicParsing
        if ($ollamaReady.StatusCode -ne 200) {
            throw "Ollama returned HTTP $($ollamaReady.StatusCode)"
        }

        Write-TunnelLog "Starting reverse SSH tunnel."
        & ssh.exe `
            -N -T `
            -i $SshKey `
            -o BatchMode=yes `
            -o IdentitiesOnly=yes `
            -o ExitOnForwardFailure=yes `
            -o ServerAliveInterval=30 `
            -o ServerAliveCountMax=3 `
            -o ConnectTimeout=10 `
            -R "127.0.0.1:11434:127.0.0.1:11434" `
            "$VpsUser@$VpsHost" 2>> $LogFile

        Write-TunnelLog "SSH tunnel exited with code $LASTEXITCODE; reconnecting in 10 seconds."
    }
    catch {
        Write-TunnelLog "Tunnel prerequisite failed: $($_.Exception.Message); retrying in 10 seconds."
    }

    Start-Sleep -Seconds 10
}
