$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot "paper_monitor_system\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error ".venv not found. Run setup_local.bat first."
    exit 1
}

# V3.1 delegates logging to Python instead of piping native stderr through
# PowerShell 5.1. This avoids harmless Git stderr lines being converted into
# NativeCommandError when ErrorActionPreference=Stop.
& $python -m paper_monitor_system.app.run_logged --provider all --initial-days 1
$code = $LASTEXITCODE
exit $code
