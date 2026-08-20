@echo off
setlocal
cd /d "%~dp0"
if not exist "paper_monitor_system\.venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Run setup_local.bat first.
  pause
  exit /b 1
)
"paper_monitor_system\.venv\Scripts\python.exe" -m paper_monitor_system.app.browser_warmup
set "code=%errorlevel%"
echo.
pause
exit /b %code%
