@echo off
setlocal
cd /d "%~dp0"
python -m paper_monitor_system.app.connection_test
set RC=%ERRORLEVEL%
echo.
pause
exit /b %RC%
