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
    # The dedicated tunnel account, not root. sshd confines it to remote
    # forwarding of 127.0.0.1:11435-11437 with no TTY, no agent forwarding and a
    # forced command, so a laptop key that leaks cannot be used for anything
    # else. Praveen's older tunnel still connects as root; that is the weaker
    # path and should be migrated onto this account.
    [string]$VpsUser = "teleautomation-tunnel",
    [int]$LocalOllamaPort = 11434,
    [int]$RetrySeconds = 10
)

$ErrorActionPreference = "Continue"

$SshKey = Join-Path $env:USERPROFILE ".ssh\teleautomation_vps_ed25519"

function Resolve-LogDirectory {
    <#
        Defensive only. Join-Path throws when handed a null, so if LOCALAPPDATA
        were ever absent both $LogDir and $LogFile would end up null and every
        Write-TunnelLog would fail silently — the tunnel running perfectly while
        producing no log at all, which is precisely the case someone needs the
        log for. Deriving from the first rooted candidate removes that failure
        mode, and throwing beats degrading to silence.

        This was NOT observed in production. It was reported as a live incident
        and that report was mistaken: the log was being written correctly all
        along, and the reader was inside an MSIX container that redirects
        %LOCALAPPDATA% to a private per-app copy. The hardening is still worth
        keeping, but nothing here was ever broken. To read the real file from a
        containerised shell, go through \\localhost\C$\... instead.

        USERPROFILE is reliably present (ssh finds its key by it), so derive
        from that, and only fall back to TEMP if even it is gone.
    #>
    foreach ($base in @(
        $env:LOCALAPPDATA,
        $(if ($env:USERPROFILE) { Join-Path $env:USERPROFILE "AppData\Local" }),
        $env:TEMP
    )) {
        if ([string]::IsNullOrWhiteSpace($base)) { continue }
        if (-not [System.IO.Path]::IsPathRooted($base)) { continue }
        return (Join-Path $base "TeleAutomation\logs")
    }
    throw "No usable location for the tunnel log: LOCALAPPDATA, USERPROFILE and TEMP are all unset."
}

$LogDir = Resolve-LogDirectory
$LogFile = Join-Path $LogDir "ollama-tunnel-$NodeName.log"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Write-TunnelLog {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    # Pinned, because Add-Content defaults to the system ANSI codepage.
    Add-Content -LiteralPath $LogFile -Value "[$timestamp] $Message" -Encoding utf8
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

            # `2>> $LogFile` writes UTF-16LE on Windows PowerShell 5.1, so
            # ssh's own errors landed in a different encoding from every other
            # line in the file and the log became unreadable — exactly when
            # someone is trying to diagnose a dead tunnel. Capture stderr to
            # its own file and fold it back through the normal logger, so the
            # whole log is one encoding.
            $sshArgs = @(
                "-N", "-T",
                "-i", $SshKey,
                "-o", "BatchMode=yes",
                "-o", "IdentitiesOnly=yes",
                "-o", "StrictHostKeyChecking=yes",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-o", "ConnectTimeout=10",
                "-R", "127.0.0.1:${VpsPort}:127.0.0.1:${LocalOllamaPort}",
                "$VpsUser@$VpsHostName"
            )
            $stderrFile = Join-Path $env:TEMP "ollama-tunnel-$NodeName.stderr"
            $process = Start-Process -FilePath "ssh.exe" `
                -ArgumentList $sshArgs `
                -NoNewWindow -Wait -PassThru `
                -RedirectStandardError $stderrFile

            if (Test-Path -LiteralPath $stderrFile) {
                Get-Content -LiteralPath $stderrFile |
                    Where-Object { $_ -and $_.Trim() } |
                    ForEach-Object { Write-TunnelLog "ssh: $_" }
                Remove-Item -LiteralPath $stderrFile -Force -ErrorAction SilentlyContinue
            }

            Write-TunnelLog "SSH exited with code $($process.ExitCode); reconnecting in $RetrySeconds seconds."
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
