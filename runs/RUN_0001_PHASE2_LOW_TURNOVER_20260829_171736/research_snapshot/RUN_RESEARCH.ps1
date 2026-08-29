$ErrorActionPreference = "Stop"
$ResearchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ResearchRoot

Write-Host "=== BTCUSDT OFFICIAL RESEARCH (COMPUTE ONLY) ===" -ForegroundColor Cyan
python .\run_phase2_low_turnover.py
if ($LASTEXITCODE -ne 0) { throw "Research failed." }
Write-Host "Research complete: results\phase2_low_turnover" -ForegroundColor Green
Write-Host "No visualization or GitHub publishing is performed from this Desktop workspace." -ForegroundColor Yellow
