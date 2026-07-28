$ErrorActionPreference = "Continue"

$VpsHostName = "187.127.169.159"
$VpsUser = "root"
$SshKey = Join-Path $env:USERPROFILE ".ssh\teleautomation_vps_ed25519"
$LogDir = Join-Path $env:LOCALAPPDATA "TeleAutomation\logs"
$LogFile = Join-Path $LogDir "ollama-secondary-tunnel.log"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Write-TunnelLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $LogFile -Value "[$timestamp] $Message"
}

if (-not (Test-Path -LiteralPath $SshKey)) {
    Write-TunnelLog "Dedicated SSH key not found."
    exit 1
}

while ($true) {
    try {
        $ollamaReady = Invoke-WebRequest `
            -Uri "http://127.0.0.1:11434/api/tags" `
            -TimeoutSec 5 `
            -UseBasicParsing
        if ($ollamaReady.StatusCode -ne 200) {
            throw "Local Ollama health check failed."
        }

        Write-TunnelLog "Starting secondary reverse SSH tunnel on VPS port 11436."
        & ssh.exe `
            -N -T `
            -i $SshKey `
            -o BatchMode=yes `
            -o IdentitiesOnly=yes `
            -o StrictHostKeyChecking=yes `
            -o ExitOnForwardFailure=yes `
            -o ServerAliveInterval=30 `
            -o ServerAliveCountMax=3 `
            -o ConnectTimeout=10 `
            -R "127.0.0.1:11436:127.0.0.1:11434" `
            "$VpsUser@$VpsHostName" 2>> $LogFile

        Write-TunnelLog "SSH tunnel exited with code $LASTEXITCODE; reconnecting in 10 seconds."
    }
    catch {
        Write-TunnelLog "Tunnel prerequisite failed; retrying in 10 seconds."
    }

    Start-Sleep -Seconds 10
}
