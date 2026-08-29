$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$Source = ".\reports\quant_research_dashboard.html"
$Target = ".\docs\index.html"

if (-not (Test-Path $Source)) {
    throw "Source report not found: $Source"
}

Copy-Item $Source $Target -Force
Write-Host "Updated fixed website entry: $Target" -ForegroundColor Green
