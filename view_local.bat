@echo off
setlocal
cd /d "%~dp0"
if not exist "paper_monitor_system\.venv\Scripts\python.exe" (
  echo .venv not found. Run setup_local.bat first.
  pause
  exit /b 1
)
start "" http://localhost:8000/paper-monitor/
paper_monitor_system\.venv\Scripts\python.exe -m http.server 8000
