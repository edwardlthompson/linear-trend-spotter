# Open a PR to microsoft/winget-pkgs with the tray notifier manifest.
# Requires: gh CLI authenticated, LTS_TRAY_RELEASE_URL (GitHub release asset URL), optional LTS_TRAY_SHA256.
param(
    [string]$ManifestPath = (Join-Path $PSScriptRoot "..\clients\windows\winget\LinearTrendSpotter.TrayNotifier.yaml"),
    [string]$ReleaseUrl = $env:LTS_TRAY_RELEASE_URL,
    [string]$Sha256 = $env:LTS_TRAY_SHA256
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "gh CLI required. Install GitHub CLI and run: gh auth login"
    exit 1
}

if (-not $ReleaseUrl) {
    Write-Error "Set LTS_TRAY_RELEASE_URL to the portable zip asset URL from GitHub Releases."
    exit 1
}

$ManifestPath = (Resolve-Path $ManifestPath).Path
$manifest = Get-Content $ManifestPath -Raw
$manifest = $manifest -replace '(?m)^(\s*InstallerUrl:\s*).*$', "`${1}$ReleaseUrl"
if ($Sha256) {
    $manifest = $manifest -replace '(?m)^(\s*InstallerSha256:\s*).*$', "`${1}$Sha256"
}

$pkgId = "EdwardLThompson.LinearTrendSpotterTrayNotifier"
$version = "0.1.0"
$branch = "lts-tray-notifier-$version"
$forkOwner = (gh api user -q .login)
$work = Join-Path $env:TEMP "winget-pkgs-$forkOwner"
$upstream = "https://github.com/microsoft/winget-pkgs.git"

if (-not (Test-Path $work)) {
    gh repo fork microsoft/winget-pkgs --clone --remote=true $work
} else {
    Push-Location $work
    git fetch origin
    git checkout master 2>$null; if ($LASTEXITCODE -ne 0) { git checkout main }
    git pull --ff-only
    Pop-Location
}

Push-Location $work
git checkout -B $branch
$destDir = Join-Path $work "manifests\e\EdwardLThompson\LinearTrendSpotterTrayNotifier\$version"
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
Set-Content -Path (Join-Path $destDir "EdwardLThompson.LinearTrendSpotterTrayNotifier.yaml") -Value $manifest -Encoding utf8NoBOM
git add .
git commit -m "Add EdwardLThompson.LinearTrendSpotterTrayNotifier $version"
git push -u origin $branch
$prUrl = gh pr create --repo microsoft/winget-pkgs --head "${forkOwner}:${branch}" --title "EdwardLThompson.LinearTrendSpotterTrayNotifier $version" --body @"
## Summary
- FOSS Windows tray notifier for Linear Trend Spotter qualified-list alerts
- Portable zip from GitHub Releases: $ReleaseUrl

## Test plan
- [ ] winget validate passed locally
- [ ] Microsoft maintainer review
"@
Pop-Location

Write-Host "PR created: $prUrl"
Write-Host "Note: Microsoft winget-pkgs maintainer merge is still required ([HUMAN] external review)."
