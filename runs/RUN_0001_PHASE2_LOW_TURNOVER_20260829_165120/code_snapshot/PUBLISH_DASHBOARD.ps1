param(
    [string]$Message = "Update BTCUSDT quant research"
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git not available in PATH." }
if (-not (Test-Path ".git")) { throw "This folder is not a Git repository." }

Write-Host "[1/3] Staging all non-ignored changes..." -ForegroundColor Cyan
git add -A
if ($LASTEXITCODE -ne 0) { throw "git add failed" }

$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "No changes to publish." -ForegroundColor Yellow
    exit 0
}

Write-Host "[2/3] Committing..." -ForegroundColor Cyan
git commit -m $Message
if ($LASTEXITCODE -ne 0) { throw "git commit failed" }

Write-Host "[3/3] Pushing main..." -ForegroundColor Cyan
git push origin main
if ($LASTEXITCODE -ne 0) { throw "git push failed" }

Write-Host "GitHub now contains code + compact results + run history." -ForegroundColor Green
