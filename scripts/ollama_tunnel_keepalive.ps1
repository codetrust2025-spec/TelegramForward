<#
.SYNOPSIS
    Keeps a laptop's local Ollama reachable from the VPS over a reverse SSH tunnel.

.DESCRIPTION
    Generalises ollama_secondary_tunnel_keepalive.ps1 so every laptop in the
    inference pool runs the same code and differs only by -VpsPort.

    Ollama itself is never exposed to the network: it stays on the laptop's own
    127.0.0.1:11434, and the tunnel publishes it on the VPS loopback only. The
    -R target is written as 127.0.0.1:<port> explicitly so the VPS listener can
    never land on 0.0.0.0 even if sshd is configured with GatewayPorts.

    Pool ports:
        11435  Jagadeesh
        11436  Praveen
        11437  RTX 4060

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File ollama_tunnel_keepalive.ps1 -VpsPort 11437 -NodeName rtx4060
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1024, 65535)]
    [int]$VpsPort,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9_]+$')]
    [string]$NodeName,

    [string]$VpsHostName = "187.127.169.159",
    [string]$VpsUser = "root",
    [int]$LocalOllamaPort = 11434,
    [int]$RetrySeconds = 10
)

$ErrorActionPreference = "Continue"

$SshKey = Join-Path $env:USERPROFILE ".ssh\teleautomation_vps_ed25519"
$LogDir = Join-Path $env:LOCALAPPDATA "TeleAutomation\logs"
$LogFile = Join-Path $LogDir "ollama-tunnel-$NodeName.log"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Write-TunnelLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $LogFile -Value "[$timestamp] $Message"
}

# One tunnel per laptop. Two processes racing for the same VPS port means one
# of them dies on every reconnect and the logs stop meaning anything.
$mutexName = "Global\TeleAutomationOllamaTunnel_$NodeName"
$createdNew = $false
$mutex = New-Object System.Threading.Mutex($true, $mutexName, [ref]$createdNew)
if (-not $createdNew) {
    Write-TunnelLog "Another tunnel process for $NodeName is already running; exiting."
    exit 0
}

if (-not (Test-Path -LiteralPath $SshKey)) {
    Write-TunnelLog "Dedicated SSH key not found at $SshKey. Create it and install the public half on the VPS."
    exit 1
}

Write-TunnelLog "Supervisor started for $NodeName -> VPS 127.0.0.1:$VpsPort"

try {
    while ($true) {
        try {
            $ollamaReady = Invoke-WebRequest `
                -Uri "http://127.0.0.1:$LocalOllamaPort/api/tags" `
                -TimeoutSec 5 `
                -UseBasicParsing
            if ($ollamaReady.StatusCode -ne 200) {
                throw "Local Ollama health check failed."
            }

            Write-TunnelLog "Starting reverse tunnel: VPS 127.0.0.1:$VpsPort -> laptop 127.0.0.1:$LocalOllamaPort"
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
                -R "127.0.0.1:${VpsPort}:127.0.0.1:${LocalOllamaPort}" `
                "$VpsUser@$VpsHostName" 2>> $LogFile

            Write-TunnelLog "SSH exited with code $LASTEXITCODE; reconnecting in $RetrySeconds seconds."
        }
        catch {
            Write-TunnelLog "Prerequisite failed ($($_.Exception.Message)); retrying in $RetrySeconds seconds."
        }

        Start-Sleep -Seconds $RetrySeconds
    }
}
finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
