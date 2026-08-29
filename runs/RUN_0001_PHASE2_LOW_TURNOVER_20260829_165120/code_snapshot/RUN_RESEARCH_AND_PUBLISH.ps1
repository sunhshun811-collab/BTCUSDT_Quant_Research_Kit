param(
    [string]$Phase = "REAL_PHASE1",
    [switch]$RebuildDataset,
    [switch]$Download,
    [int]$Workers = 8,
    [switch]$NoPublish
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "=== RUN RESEARCH + ARCHIVE + GITHUB + DESKTOP PACKAGE ===" -ForegroundColor Cyan

if ($Download) {
    Write-Host "[1/7] Refreshing Binance archives..." -ForegroundColor Cyan
    python .\download_phase1_data.py --mode core --workers $Workers
    if ($LASTEXITCODE -ne 0) { throw "Download failed." }
} else {
    Write-Host "[1/7] Download skipped." -ForegroundColor DarkGray
}

if ($RebuildDataset) {
    Write-Host "[2/7] Rebuilding dataset..." -ForegroundColor Cyan
    python .\build_phase1_dataset.py
    if ($LASTEXITCODE -ne 0) { throw "Dataset build failed." }
} else {
    Write-Host "[2/7] Dataset rebuild skipped." -ForegroundColor DarkGray
}

Write-Host "[3/7] Running research..." -ForegroundColor Cyan
python .\run_phase1_research.py
if ($LASTEXITCODE -ne 0) { throw "Research failed." }

Write-Host "[4/7] Archiving immutable research run..." -ForegroundColor Cyan
python .\src\research_archive.py --phase $Phase
if ($LASTEXITCODE -ne 0) { throw "Archive failed." }

if (Test-Path ".\src\github_pages_api_mirror.py") {
    Write-Host "[5/7] Updating GitHub Pages compact mirror..." -ForegroundColor Cyan
    python .\src\github_pages_api_mirror.py
    if ($LASTEXITCODE -ne 0) { throw "Research API mirror failed." }
} else {
    Write-Host "[5/7] API mirror module not present; skipped." -ForegroundColor DarkGray
}

if ($NoPublish) {
    Write-Host "[6/7] GitHub publish skipped by -NoPublish." -ForegroundColor Yellow
} else {
    Write-Host "[6/7] Committing and pushing repository..." -ForegroundColor Cyan
    & .\PUBLISH_DASHBOARD.ps1 -Message "Research run: $Phase"
    if ($LASTEXITCODE -ne 0) { throw "GitHub publish failed." }
}

Write-Host "[7/7] Building compact ZIP on Desktop..." -ForegroundColor Cyan
& .\BUILD_RESEARCH_PACKAGE.ps1
if ($LASTEXITCODE -ne 0) { throw "Desktop research package failed." }

Write-Host ""
Write-Host "ALL COMPLETE" -ForegroundColor Green
Write-Host "Next step: drag Desktop\research_package_latest.zip into ChatGPT." -ForegroundColor Yellow
