@echo off
setlocal
cd /d "%~dp0"
python -m paper_monitor_system.app.sync --provider all --initial-days 2
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" echo FETCH FAILED. Exit code: %RC%
pause
exit /b %RC%
