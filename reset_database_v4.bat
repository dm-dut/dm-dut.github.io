@echo off
setlocal
cd /d "%~dp0"
echo This permanently deletes the local paper-monitor database and generated JSON.
choice /C YN /M "Continue"
if errorlevel 2 exit /b 0
python -m paper_monitor_system.app.reset_database
pause
