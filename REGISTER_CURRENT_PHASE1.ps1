param(
    [string]$Phase = "REAL_PHASE1",
    [switch]$Publish
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "=== REGISTER CURRENT RESEARCH RUN ===" -ForegroundColor Cyan
Write-Host "This does NOT rerun the backtest." -ForegroundColor Yellow

if (-not (Test-Path ".\results\phase1\alpha_leaderboard.csv")) {
    throw "Missing results\phase1\alpha_leaderboard.csv. Run Phase1 first."
}

python .\src\research_archive.py --phase $Phase
if ($LASTEXITCODE -ne 0) { throw "Research archive failed." }

Write-Host "Created immutable history under .\runs\" -ForegroundColor Green
Write-Host "Updated stable snapshot under .\latest\" -ForegroundColor Green

if ($Publish) {
    & .\PUBLISH_DASHBOARD.ps1 -Message "Archive current BTCUSDT research run"
    if ($LASTEXITCODE -ne 0) { throw "GitHub publish failed." }
} else {
    Write-Host '.\PUBLISH_DASHBOARD.ps1 -Message "Archive current BTCUSDT research run"' -ForegroundColor Yellow
}
