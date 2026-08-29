param(
    [ValidateSet("core","full")]
    [string]$Mode = "core",
    [int]$Workers = 8,
    [switch]$SkipDownload,
    [switch]$Publish
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "=== BTCUSDT REAL PHASE 1 ===" -ForegroundColor Cyan
Write-Host "Mode: $Mode | Test set: LOCKED" -ForegroundColor Yellow

Write-Host "[1/5] Installing/updating Python dependencies..." -ForegroundColor Cyan
python -m pip install -r .\requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

if (-not $SkipDownload) {
    Write-Host "[2/5] Downloading Binance public archives (resume-safe)..." -ForegroundColor Cyan
    python .\download_phase1_data.py --mode $Mode --workers $Workers
    if ($LASTEXITCODE -ne 0) { throw "download failed; rerun the same command to resume" }
} else {
    Write-Host "[2/5] Download skipped." -ForegroundColor Yellow
}

Write-Host "[3/5] Building validated Parquet dataset..." -ForegroundColor Cyan
python .\build_phase1_dataset.py
if ($LASTEXITCODE -ne 0) { throw "dataset build failed" }

Write-Host "[4/5] Running real Train/Validation Alpha baseline..." -ForegroundColor Cyan
python .\run_phase1_research.py
if ($LASTEXITCODE -ne 0) { throw "research failed" }

Write-Host "[5/5] Dashboard updated: .\docs\index.html" -ForegroundColor Green

if ($Publish) {
    Write-Host "Publishing fixed GitHub Pages dashboard..." -ForegroundColor Cyan
    & .\PUBLISH_DASHBOARD.ps1 -Message "Real Phase1 BTCUSDT alpha baseline"
} else {
    Write-Host ""
    Write-Host "Review locally first. Then publish with:" -ForegroundColor Yellow
    Write-Host '.\PUBLISH_DASHBOARD.ps1 -Message "Real Phase1 BTCUSDT alpha baseline"'
}
