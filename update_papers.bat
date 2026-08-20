@echo off
setlocal
cd /d "%~dp0"

if not exist "paper_monitor_system\.venv\Scripts\python.exe" (
  echo ERROR: .venv not found. Run setup_local.bat first.
  echo.
  pause
  exit /b 1
)

"paper_monitor_system\.venv\Scripts\python.exe" -m paper_monitor_system.app.run_logged --provider all --initial-days 7
set "code=%errorlevel%"

echo.
if "%code%"=="0" (
  echo Update completed successfully.
) else (
  echo Update failed with exit code %code%.
  echo Logs are in paper_monitor_system\logs\
)
echo.
echo Press any key to close this manual-update window.
pause >nul
exit /b %code%
