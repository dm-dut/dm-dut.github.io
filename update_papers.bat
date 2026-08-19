@echo off
setlocal
cd /d "%~dp0"
if not exist "paper_monitor_system\.venv\Scripts\python.exe" (
  echo .venv not found. Run setup_local.bat first.
  pause
  exit /b 1
)
call paper_monitor_system\.venv\Scripts\activate.bat
python -m paper_monitor_system.app.local_update --provider all --initial-days 1
set ERR=%errorlevel%
echo.
if %ERR%==0 (
  echo Paper monitor update completed.
) else (
  echo Paper monitor update FAILED with exit code %ERR%.
)
pause
exit /b %ERR%
