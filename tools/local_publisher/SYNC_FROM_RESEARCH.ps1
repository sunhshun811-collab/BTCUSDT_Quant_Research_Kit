param(
    [Parameter(Mandatory=$true)]
    [string]$ResearchRoot,
    [switch]$ForceRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

Write-Host "=== SYNC RESEARCH -> GITHUB ===" -ForegroundColor Cyan
Write-Host "Research workspace: $ResearchRoot"
Write-Host "Git publisher repo : $RepoRoot"

git fetch origin
if ($LASTEXITCODE -ne 0) { throw "git fetch failed" }

git pull --rebase origin main
if ($LASTEXITCODE -ne 0) { throw "git pull --rebase failed" }

$Desktop = [Environment]::GetFolderPath("Desktop")
$Package = Join-Path $Desktop "research_package_latest.zip"

$Args = @(
    ".\tools\local_publisher\sync_from_research.py",
    "--repo-root", "$RepoRoot",
    "--research-root", "$ResearchRoot",
    "--package-output", "$Package"
)
if ($ForceRun) { $Args += "--force-run" }

python @Args
if ($LASTEXITCODE -ne 0) { throw "research sync failed" }

git add -A
$Changes = git status --porcelain
if ($Changes) {
    git commit -m "Sync official Phase2 research"
    if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
    git push origin main
    if ($LASTEXITCODE -ne 0) { throw "git push failed" }
    Write-Host "GitHub updated. Pages deployment has been triggered." -ForegroundColor Green
} else {
    Write-Host "No repository changes to commit." -ForegroundColor DarkGray
}

Write-Host "Desktop handoff package: $Package" -ForegroundColor Green
Write-Host "Visualization: https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/" -ForegroundColor Yellow
