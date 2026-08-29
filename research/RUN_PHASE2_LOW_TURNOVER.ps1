param(
    [switch]$SkipInstall,
    [switch]$OpenReport
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "=== BTCUSDT PHASE 2 LOW-TURNOVER RESEARCH ===" -ForegroundColor Cyan
Write-Host "Test set remains physically locked." -ForegroundColor Yellow

$DataPath = Join-Path $ProjectRoot "data\processed\btc_core_1m_2020_2025.parquet"
if (-not (Test-Path -LiteralPath $DataPath)) {
    throw "Missing processed data: $DataPath. Run RUN_PHASE1_CORE.ps1 first."
}

if (-not $SkipInstall) {
    Write-Host "[1/2] Checking Python dependencies..." -ForegroundColor Cyan
    python -m pip install -r .\requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
} else {
    Write-Host "[1/2] Dependency installation skipped." -ForegroundColor DarkGray
}

Write-Host "[2/2] Running low-turnover Train/Validation research..." -ForegroundColor Cyan
python .\run_phase2_low_turnover.py
if ($LASTEXITCODE -ne 0) { throw "Phase 2 research failed." }

$Report = Join-Path $ProjectRoot "reports\phase2_low_turnover_dashboard.html"
Write-Host "COMPLETE" -ForegroundColor Green
Write-Host "Leaderboard: .\results\phase2_low_turnover\alpha_leaderboard.csv"
Write-Host "Cost scenarios: .\results\phase2_low_turnover\cost_sensitivity.csv"
Write-Host "Yearly stability: .\results\phase2_low_turnover\yearly_metrics.csv"
Write-Host "Dashboard: .\reports\phase2_low_turnover_dashboard.html"

if ($OpenReport) {
    Start-Process -FilePath $Report
}
