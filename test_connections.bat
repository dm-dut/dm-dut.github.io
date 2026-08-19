@echo off
setlocal
cd /d "%~dp0"
if not exist "paper_monitor_system\.venv\Scripts\python.exe" (
  echo .venv not found. Run setup_local.bat first.
  pause
  exit /b 1
)
call paper_monitor_system\.venv\Scripts\activate.bat
python -m paper_monitor_system.app.connection_test
set ERR=%errorlevel%
echo.
pause
exit /b %ERR%
