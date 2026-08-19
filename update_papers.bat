@echo off
setlocal
cd /d "%~dp0"
echo Paper monitor LOCAL V4 - Crossref only
python -m paper_monitor_system.app.run_logged --provider all --initial-days 2
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" (
  echo UPDATE FAILED. Exit code: %RC%
) else (
  echo Update completed successfully.
)
echo.
pause
exit /b %RC%
