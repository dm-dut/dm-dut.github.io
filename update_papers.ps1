$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot "paper_monitor_system\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw ".venv not found. Run setup_local.bat first."
}

$logDir = Join-Path $PSScriptRoot "paper_monitor_system\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "update_$stamp.log"

Write-Host "Paper monitor LOCAL V3 update"
Write-Host "Log: $logFile"
Write-Host ""

& $python -m paper_monitor_system.app.local_update --provider all --initial-days 1 2>&1 | Tee-Object -FilePath $logFile
$code = $LASTEXITCODE

if ($code -eq 0) {
    Write-Host ""
    Write-Host "Paper monitor update completed successfully."
} else {
    Write-Host ""
    Write-Host "Paper monitor update FAILED with exit code $code."
    Write-Host "Review: $logFile"
}
exit $code
