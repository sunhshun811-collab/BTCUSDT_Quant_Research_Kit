$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

python .\src\github_pages_api_mirror.py
if ($LASTEXITCODE -ne 0) { throw "Research API mirror failed." }
