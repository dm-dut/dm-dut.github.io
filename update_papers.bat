@echo off
setlocal
cd /d "%~dp0"

if not exist "paper_monitor_system\.venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Run setup_local.bat first.
  echo.
  pause
  exit /b 1
)

"paper_monitor_system\.venv\Scripts\python.exe" -m paper_monitor_system.app.run_logged --provider all --initial-days 1
set "code=%errorlevel%"

if not "%code%"=="0" (
  echo.
  echo Update failed. The window will stay open so you can read the error.
  echo Logs are in paper_monitor_system\logs\
  pause
)
exit /b %code%
