@echo off
setlocal
cd /d "%~dp0"

if not exist "paper_monitor_system\.venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Run setup_local.bat first.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update_papers.ps1"
exit /b %errorlevel%
