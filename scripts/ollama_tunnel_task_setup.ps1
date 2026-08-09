<#
.SYNOPSIS
    Registers the Ollama reverse-SSH tunnel as a Scheduled Task so it survives
    reboots without anyone opening a terminal.

.DESCRIPTION
    Run once per laptop, in an elevated PowerShell, from the repo's scripts
    directory. The task starts at logon and is restarted by Windows if the
    supervisor process dies; the supervisor itself handles Wi-Fi drops and VPS
    restarts by reconnecting on a loop.

    No password is stored anywhere. Authentication is the dedicated SSH key at
    %USERPROFILE%\.ssh\teleautomation_vps_ed25519, whose public half must
    already be in /home/teleautomation-tunnel/.ssh/authorized_keys on the VPS,
    carrying permitlisten="127.0.0.1:<VpsPort>" for this node's own port.

.EXAMPLE
    .\ollama_tunnel_task_setup.ps1 -VpsPort 11437 -NodeName rtx4060
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateRange(1024, 65535)][int]$VpsPort,
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-z0-9_]+$')][string]$NodeName
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "ollama_tunnel_keepalive.ps1"
if (-not (Test-Path -LiteralPath $scriptPath)) {
    throw "ollama_tunnel_keepalive.ps1 not found next to this installer."
}

$sshKey = Join-Path $env:USERPROFILE ".ssh\teleautomation_vps_ed25519"
if (-not (Test-Path -LiteralPath $sshKey)) {
    Write-Warning "SSH key missing at $sshKey."
    Write-Warning "Create it with:  ssh-keygen -t ed25519 -f `"$sshKey`" -C ollama-tunnel-$NodeName"
    Write-Warning "Then add the .pub contents to /home/teleautomation-tunnel/.ssh/authorized_keys on the VPS."
    Write-Warning "Not root's authorized_keys: the tunnel account is confined to remote forwarding of one port."
    Write-Warning "The entry needs permitlisten=`"127.0.0.1:$VpsPort`" or sshd refuses the forward."
}

$taskName = "TeleAutomation Ollama Tunnel ($NodeName)"

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ("-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass " +
               "-File `"$scriptPath`" -VpsPort $VpsPort -NodeName $NodeName")

$trigger = New-ScheduledTaskTrigger -AtLogOn

# The supervisor loops forever by design, so no execution limit, and Windows
# should bring it back rather than leave the node silently offline.
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Limited `
    -Description "Publishes this laptop's local Ollama on VPS 127.0.0.1:$VpsPort over reverse SSH." | Out-Null

Start-ScheduledTask -TaskName $taskName

Write-Host "Registered and started: $taskName"
Write-Host "Log: $(Join-Path $env:LOCALAPPDATA "TeleAutomation\logs\ollama-tunnel-$NodeName.log")"
Write-Host ""
Write-Host "Verify from the VPS:"
Write-Host "  curl -s http://127.0.0.1:$VpsPort/api/tags"
