param(
    [string]$Message = "Update BTCUSDT quant dashboard"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "[1/5] Checking Git..." -ForegroundColor Cyan
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is not installed or not available in PATH."
}

if (-not (Test-Path ".git")) {
    throw "This folder is not a Git repository yet. Complete SETUP_GITHUB_PAGES.md first."
}

Write-Host "[2/5] Checking website entry..." -ForegroundColor Cyan
if (-not (Test-Path ".\docs\index.html")) {
    throw ".\docs\index.html does not exist."
}

Write-Host "[3/5] Staging dashboard..." -ForegroundColor Cyan
git add docs .github README.md SETUP_GITHUB_PAGES.md

$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "No changes to publish." -ForegroundColor Yellow
    exit 0
}

Write-Host "[4/5] Committing..." -ForegroundColor Cyan
git commit -m $Message

Write-Host "[5/5] Pushing to main..." -ForegroundColor Cyan
git push origin main

Write-Host ""
Write-Host "Push complete. GitHub Actions will deploy the fixed Pages URL." -ForegroundColor Green
