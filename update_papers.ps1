$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot "paper_monitor_system\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error ".venv not found. Run setup_local.bat first."
    exit 1
}
& $python -m paper_monitor_system.app.run_logged --provider all --initial-days 7
exit $LASTEXITCODE
