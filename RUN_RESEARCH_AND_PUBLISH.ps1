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

Write-Host "=== RUN RESEARCH + ARCHIVE + GITHUB ===" -ForegroundColor Cyan

if ($Download) {
    Write-Host "[1/6] Refreshing Binance archives..." -ForegroundColor Cyan
    python .\download_phase1_data.py --mode core --workers $Workers
    if ($LASTEXITCODE -ne 0) { throw "Download failed." }
} else { Write-Host "[1/6] Download skipped." -ForegroundColor DarkGray }

if ($RebuildDataset) {
    Write-Host "[2/6] Rebuilding dataset..." -ForegroundColor Cyan
    python .\build_phase1_dataset.py
    if ($LASTEXITCODE -ne 0) { throw "Dataset build failed." }
} else { Write-Host "[2/6] Dataset rebuild skipped." -ForegroundColor DarkGray }

Write-Host "[3/6] Running research..." -ForegroundColor Cyan
python .\run_phase1_research.py
if ($LASTEXITCODE -ne 0) { throw "Research failed." }

Write-Host "[4/6] Archiving immutable research run..." -ForegroundColor Cyan
python .\src\research_archive.py --phase $Phase
if ($LASTEXITCODE -ne 0) { throw "Archive failed." }

Write-Host "[5/6] Updating machine-readable Pages mirror..." -ForegroundColor Cyan
python .\src\github_pages_api_mirror.py
if ($LASTEXITCODE -ne 0) { throw "Research API mirror failed." }

if ($NoPublish) {
    Write-Host "[6/6] Publish skipped." -ForegroundColor Yellow
} else {
    Write-Host "[6/6] Committing and pushing..." -ForegroundColor Cyan
    & .\PUBLISH_DASHBOARD.ps1 -Message "Research run: $Phase"
    if ($LASTEXITCODE -ne 0) { throw "GitHub publish failed." }
}

Write-Host "COMPLETE" -ForegroundColor Green
Write-Host "Repository history: runs\"
Write-Host "Stable latest: latest\"
Write-Host "Public machine mirror: docs\api\"
