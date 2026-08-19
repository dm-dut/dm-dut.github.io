@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r paper_monitor_system\requirements.txt
if not exist paper_monitor_system\.env copy paper_monitor_system\.env.example paper_monitor_system\.env >nul
echo.
echo Setup complete. Edit paper_monitor_system\.env and set CROSSREF_MAILTO.
pause
