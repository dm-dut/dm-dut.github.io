@echo off
setlocal
cd /d "%~dp0"
if not exist "paper_monitor_system\.venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Run setup_local.bat first.
  pause
  exit /b 1
)
"paper_monitor_system\.venv\Scripts\python.exe" -m paper_monitor_system.app.run_logged --provider all --initial-days 1 --no-git
set "code=%errorlevel%"
if not "%code%"=="0" pause
exit /b %code%
