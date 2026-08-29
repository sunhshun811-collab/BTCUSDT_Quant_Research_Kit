$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "=== MAKE PHASE2 THE ONLY OFFICIAL RESULT ===" -ForegroundColor Cyan
Write-Host "No research rerun will be performed." -ForegroundColor Yellow

if (-not (Test-Path ".\results\phase2_low_turnover\alpha_leaderboard.csv")) {
    throw "Missing results\phase2_low_turnover\alpha_leaderboard.csv"
}
if (-not (Test-Path ".\reports\phase2_low_turnover_dashboard.html")) {
    throw "Missing reports\phase2_low_turnover_dashboard.html"
}

Write-Host "[1/4] Promoting existing Phase2..." -ForegroundColor Cyan
python .\src\promote_phase2_only.py
if ($LASTEXITCODE -ne 0) { throw "Phase2 promotion failed." }

Write-Host "[2/4] Updating GitHub Pages API mirror if available..." -ForegroundColor Cyan
if (Test-Path ".\src\github_pages_api_mirror.py") {
    python .\src\github_pages_api_mirror.py
    if ($LASTEXITCODE -ne 0) { throw "API mirror update failed." }
} else {
    Write-Host "API mirror module not found; skipping." -ForegroundColor DarkGray
}

Write-Host "[3/4] Publishing to GitHub..." -ForegroundColor Cyan
& .\PUBLISH_DASHBOARD.ps1 -Message "Promote Phase2 as sole official research result"
if ($LASTEXITCODE -ne 0) { throw "GitHub publish failed." }

Write-Host "[4/4] Building Desktop research_package_latest.zip..." -ForegroundColor Cyan
& .\BUILD_RESEARCH_PACKAGE.ps1
if ($LASTEXITCODE -ne 0) { throw "Desktop package build failed." }

Write-Host ""
Write-Host "DONE" -ForegroundColor Green
Write-Host "Official result: PHASE2_LOW_TURNOVER only." -ForegroundColor Green
Write-Host "Older Phase1 outputs are deprecated and removed from the current working tree." -ForegroundColor Yellow
