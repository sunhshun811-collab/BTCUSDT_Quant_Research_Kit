param(
    [string]$OutputName = "research_package_latest.zip"
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$Desktop = [Environment]::GetFolderPath("Desktop")
if ([string]::IsNullOrWhiteSpace($Desktop)) {
    $Desktop = Join-Path $HOME "Desktop"
}
$Output = Join-Path $Desktop $OutputName

python .\src\research_package.py --project-root "$ProjectRoot" --output "$Output"
if ($LASTEXITCODE -ne 0) { throw "research package build failed" }

Write-Host "READY: $Output" -ForegroundColor Green
