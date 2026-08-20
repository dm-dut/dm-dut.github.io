@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo Paper Monitor LOCAL V6 ID-FIRST setup
echo ============================================================

where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo ERROR: Python 3 is not installed or not in PATH.
    echo Install Python 3.11+ and run this file again.
    pause
    exit /b 1
  )
  set "PY=python"
)

if not exist "paper_monitor_system\.venv\Scripts\python.exe" (
  echo Creating local virtual environment...
  %PY% -m venv paper_monitor_system\.venv
  if errorlevel 1 goto :fail
)

call paper_monitor_system\.venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r paper_monitor_system\requirements.txt
if errorlevel 1 goto :fail

echo.
echo Installing bundled Chromium fallback for Playwright...
python -m playwright install chromium
if errorlevel 1 (
  echo WARNING: bundled Chromium installation failed. If Microsoft Edge is installed, V6 can still use channel=msedge.
)

if not exist "paper_monitor_system\.env" (
  copy /Y "paper_monitor_system\.env.example" "paper_monitor_system\.env" >nul
  echo.
  echo Created paper_monitor_system\.env
  echo Please edit it and fill SPRINGER_API_KEY.
) else (
  echo paper_monitor_system\.env already exists; it was not overwritten.
  echo Compare it with .env.example, especially the new BROWSER_* options.
)

if not exist "paper_monitor_system\logs" mkdir "paper_monitor_system\logs"

python -m paper_monitor_system.app.selfcheck
if errorlevel 1 goto :fail
python -m paper_monitor_system.app.selftest
if errorlevel 1 goto :fail

echo.
echo Setup completed successfully.
echo Recommended next step: browser_warmup.bat, then test_connections.bat.
pause
exit /b 0

:fail
echo.
echo Setup failed. Review the error above.
pause
exit /b 1
