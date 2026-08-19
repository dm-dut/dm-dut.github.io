@echo off
setlocal
cd /d "%~dp0"
python -m paper_monitor_system.app.run_logged --provider all --initial-days 2
exit /b %ERRORLEVEL%
