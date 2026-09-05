<#
.SYNOPSIS
    Deploy this plugin to an OctoPrint host over SSH and restart the service.

.DESCRIPTION
    Copies the working tree to the OctoPrint machine, installs it into
    OctoPrint's virtualenv in editable mode, and restarts OctoPrint.

    Requires rsync and ssh on PATH (both ship with Git for Windows) and key-based
    SSH access to the target.

.EXAMPLE
    ./scripts/deploy.ps1 -Target pi@octoprint.local

.EXAMPLE
    ./scripts/deploy.ps1 -Target will@debian -OctoPrintVenv /opt/octoprint/venv -ServiceUser octoprint
#>
[CmdletBinding()]
param(
    # user@host of the machine running OctoPrint.
    [Parameter(Mandatory = $true)]
    [string]$Target,

    # Where to place the source on the remote machine.
    [string]$RemotePath = '~/OctoPrint-HomeAssistantPower',

    # OctoPrint's virtualenv on the remote machine.
    [string]$OctoPrintVenv = '~/OctoPrint/venv',

    # systemd unit name.
    [string]$Service = 'octoprint',

    # Set when OctoPrint runs as a different user than the one you SSH in as.
    [string]$ServiceUser = '',

    # Skip the pip install and only sync + restart (fast loop for template/JS edits).
    [switch]$NoInstall
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot

Write-Host "Syncing $repo -> ${Target}:$RemotePath" -ForegroundColor Cyan
rsync -az --delete `
    --exclude '.git' --exclude '.venv' --exclude '__pycache__' `
    --exclude '*.egg-info' --exclude '.pytest_cache' `
    "$repo/" "${Target}:$RemotePath/"
if ($LASTEXITCODE -ne 0) { throw "rsync failed with exit code $LASTEXITCODE" }

$commands = @()
if (-not $NoInstall) {
    $pip = "$OctoPrintVenv/bin/pip install -e $RemotePath"
    if ($ServiceUser) { $pip = "sudo -u $ServiceUser $pip" }
    $commands += $pip
}
$commands += "sudo systemctl restart $Service"

$remoteCommand = $commands -join ' && '
Write-Host "Running on ${Target}: $remoteCommand" -ForegroundColor Cyan
ssh $Target $remoteCommand
if ($LASTEXITCODE -ne 0) { throw "Remote command failed with exit code $LASTEXITCODE" }

Write-Host 'Deployed. Reload the OctoPrint UI with a hard refresh (Ctrl+Shift+R).' -ForegroundColor Green
