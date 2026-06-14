# Validate winget manifest for the Windows tray notifier.
# Skips gracefully when winget CLI is not installed (local dev / CI without Windows).
param(
    [string]$ManifestPath = (Join-Path $PSScriptRoot "..\clients\windows\winget\LinearTrendSpotter.TrayNotifier.yaml")
)

$ErrorActionPreference = "Stop"
$ManifestPath = (Resolve-Path $ManifestPath).Path

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "SKIP: winget CLI not found — manifest not validated ($ManifestPath)"
    exit 0
}

Write-Host "Validating $ManifestPath ..."
winget validate --manifest $ManifestPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "winget validate failed"
    exit $LASTEXITCODE
}
Write-Host "OK"
