@echo off
setlocal
cd /d "%~dp0"
echo This will delete the local paper-monitor database and public JSON.
choice /C YN /N /M "Continue? [Y/N] "
if errorlevel 2 exit /b 0
if exist "paper_monitor_system\data\papers.db" del /Q "paper_monitor_system\data\papers.db"
if exist "paper-monitor\data\online_papers.json" del /Q "paper-monitor\data\online_papers.json"
echo Database/JSON removed. The next update will create a fresh V6 database.
pause
