@echo off
setlocal
cd /d "%~dp0"
if not exist "paper_monitor_system\.venv\Scripts\python.exe" exit /b 1
"paper_monitor_system\.venv\Scripts\python.exe" -m paper_monitor_system.app.run_logged --provider all --initial-days 7 --skip-tests
exit /b %errorlevel%
