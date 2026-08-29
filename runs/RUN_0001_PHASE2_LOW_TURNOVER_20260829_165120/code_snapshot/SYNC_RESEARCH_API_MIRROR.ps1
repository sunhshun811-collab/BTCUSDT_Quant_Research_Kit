param(
    [switch]$Publish
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "=== SYNC RESEARCH API MIRROR ===" -ForegroundColor Cyan

if (-not (Test-Path ".\latest\research_state.json")) {
    throw "latest\research_state.json not found. Run REGISTER_CURRENT_PHASE1.ps1 first."
}

python .\src\github_pages_api_mirror.py
if ($LASTEXITCODE -ne 0) { throw "API mirror generation failed." }

Write-Host ""
Write-Host "Local machine-readable URLs will be published under docs\api\" -ForegroundColor Green

if ($Publish) {
    & .\PUBLISH_DASHBOARD.ps1 -Message "Publish machine-readable research API mirror"
    if ($LASTEXITCODE -ne 0) { throw "Publish failed." }
} else {
    Write-Host "To publish:" -ForegroundColor Yellow
    Write-Host '.\PUBLISH_DASHBOARD.ps1 -Message "Publish machine-readable research API mirror"'
}
