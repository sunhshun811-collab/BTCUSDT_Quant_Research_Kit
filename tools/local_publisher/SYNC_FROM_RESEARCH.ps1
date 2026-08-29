param([Parameter(Mandatory=$true)][string]$ResearchRoot,[switch]$ForceRun)
$ErrorActionPreference="Stop"
$RepoRoot=Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot
function Invoke-GitRetry { param([string[]]$GitArgs,[string]$Name)
  for($i=1;$i -le 4;$i++){ Write-Host "$Name attempt $i / 4..." -ForegroundColor DarkGray
    & git -c http.version=HTTP/1.1 @GitArgs
    if($LASTEXITCODE -eq 0){return}
    Start-Sleep -Seconds (3*$i)
  }
  throw "$Name failed after 4 retries."
}
Write-Host "=== RESEARCH -> GITHUB -> PAGES ===" -ForegroundColor Cyan
Invoke-GitRetry -GitArgs @("fetch","origin") -Name "git fetch"
& git rebase origin/main
if($LASTEXITCODE -ne 0){throw "git rebase origin/main failed"}
$Args=@(".\tools\local_publisher\sync_from_research.py","--repo-root","$RepoRoot","--research-root","$ResearchRoot")
if($ForceRun){$Args+="--force-run"}
python @Args
if($LASTEXITCODE -ne 0){throw "research sync failed"}
git add research official runs
$Changes=git status --porcelain
if($Changes){
  git commit -m "Sync official Phase2 research"
  if($LASTEXITCODE -ne 0){throw "git commit failed"}
  Invoke-GitRetry -GitArgs @("push","origin","main") -Name "git push"
  Write-Host "GitHub updated. Actions will rebuild Dashboard + ChatGPT ZIP." -ForegroundColor Green
}else{Write-Host "No research/code Git change." -ForegroundColor DarkGray}
Write-Host "Dashboard: https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/" -ForegroundColor Yellow
Write-Host "ZIP: https://sunhshun811-collab.github.io/BTCUSDT_Quant_Research_Kit/downloads/research_package_latest.zip" -ForegroundColor Yellow
