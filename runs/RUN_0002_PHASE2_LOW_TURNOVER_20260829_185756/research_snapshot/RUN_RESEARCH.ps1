$ErrorActionPreference="Stop"
$ResearchRoot=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ResearchRoot
Write-Host "=== BTCUSDT OFFICIAL RESEARCH ===" -ForegroundColor Cyan
Write-Host "[1/2] Running factor research..." -ForegroundColor Cyan
python .\run_phase2_low_turnover.py
if($LASTEXITCODE -ne 0){throw "Research failed."}
Write-Host "[2/2] Syncing code/results to GitHub..." -ForegroundColor Cyan
$PublisherSync=Join-Path $env:LOCALAPPDATA "BTCUSDT_Quant_Research_Kit_publish\tools\local_publisher\SYNC_FROM_RESEARCH.ps1"
if(-not(Test-Path $PublisherSync)){throw "External GitHub publisher not found: $PublisherSync"}
& $PublisherSync -ResearchRoot $ResearchRoot
if($LASTEXITCODE -ne 0){throw "GitHub sync failed."}
Write-Host "RESEARCH LOOP COMPLETE" -ForegroundColor Green
Write-Host "Dashboard: https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/" -ForegroundColor Yellow
Write-Host "Wait for Actions to turn green, then click the ChatGPT ZIP download button." -ForegroundColor Yellow
