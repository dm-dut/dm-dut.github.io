$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path "paper_monitor_system\.venv\Scripts\python.exe")) {
    throw ".venv not found. Run setup_local.bat first."
}
& "paper_monitor_system\.venv\Scripts\python.exe" -m paper_monitor_system.app.local_update --provider all --initial-days 7
exit $LASTEXITCODE
