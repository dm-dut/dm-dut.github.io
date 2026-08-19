@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo Paper Monitor LOCAL_FINAL_V2 setup
echo ============================================================

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo ERROR: Python 3 is not installed or not in PATH.
    echo Install Python 3.11 or 3.12, then run this file again.
    pause
    exit /b 1
  )
  set "PY=python"
)

if not exist "paper_monitor_system\.venv\Scripts\python.exe" (
  echo Creating local virtual environment in paper_monitor_system\.venv ...
  %PY% -m venv paper_monitor_system\.venv
  if errorlevel 1 goto :fail
)

call paper_monitor_system\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r paper_monitor_system\requirements.txt
if errorlevel 1 goto :fail

if not exist "paper_monitor_system\.env" (
  copy /Y "paper_monitor_system\.env.example" "paper_monitor_system\.env" >nul
  echo.
  echo Created paper_monitor_system\.env
  echo Please open it in Notepad and fill SPRINGER_API_KEY and CROSSREF_MAILTO. ELSEVIER_API_KEY is optional in LOCAL V2.
) else (
  echo paper_monitor_system\.env already exists; it was not overwritten.
)

echo.
python -m paper_monitor_system.app.selfcheck
if errorlevel 1 goto :fail
python -m paper_monitor_system.app.selftest
if errorlevel 1 goto :fail

echo.
echo Setup completed successfully.
echo Next: edit paper_monitor_system\.env, then double-click test_connections.bat.
pause
exit /b 0

:fail
echo.
echo Setup failed. Review the error above.
pause
exit /b 1
