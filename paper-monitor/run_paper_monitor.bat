@echo off
setlocal EnableExtensions

REM ========================================================
REM Paper Monitor local update + GitHub publish
REM
REM Place this file in:
REM   dm-dut.github.io\paper-monitor\run_paper_monitor.bat
REM
REM Local work:
REM   1. update.py
REM   2. generate_email.py
REM
REM GitHub publish:
REM   3. commit/push generated JSON + email HTML
REM
REM GitHub Actions then sends the email when
REM web\latest_email.json changes.
REM
REM NOTE:
REM update.py output is shown live in this window AND
REM appended to logs\scheduled_run.log.
REM ========================================================

set "PROJECT_ROOT=%~dp0"

for %%I in ("%PROJECT_ROOT%..") do set "REPO_ROOT=%%~fI"

REM If Task Scheduler cannot find Python, replace "python"
REM with the full path to python.exe.
set "PYTHON_EXE=python"

cd /d "%PROJECT_ROOT%"

if not exist "logs" mkdir "logs"
set "LOG_FILE=%PROJECT_ROOT%logs\scheduled_run.log"

echo.>> "%LOG_FILE%"
echo ========================================================>> "%LOG_FILE%"
echo Paper Monitor run started: %date% %time%>> "%LOG_FILE%"
echo ========================================================>> "%LOG_FILE%"

REM ========================================================
REM 1. Update local database and JSON
REM    Show progress in console + save to log
REM ========================================================

echo [1/3] Updating Paper Monitor data...
echo [1/3] update.py>> "%LOG_FILE%"

powershell -NoProfile -Command ^
  "& '%PYTHON_EXE%' 'scripts\update.py' 2>&1 | Tee-Object -FilePath '%LOG_FILE%' -Append; exit $LASTEXITCODE"

if errorlevel 1 (
    echo ERROR: update.py failed.
    echo ERROR: update.py failed.>> "%LOG_FILE%"
    exit /b 1
)

REM ========================================================
REM 2. Generate current email HTML locally
REM
REM If there are no new papers, generate_email.py exits
REM normally and latest_email.json remains unchanged.
REM ========================================================

echo [2/3] Generating email HTML...
echo [2/3] generate_email.py>> "%LOG_FILE%"

"%PYTHON_EXE%" scripts\generate_email.py >> "%LOG_FILE%" 2>&1

if errorlevel 1 (
    echo ERROR: generate_email.py failed.
    echo ERROR: generate_email.py failed.>> "%LOG_FILE%"
    exit /b 1
)

REM ========================================================
REM 3. Commit and push generated frontend data/email files
REM ========================================================

echo [3/3] Publishing generated files to GitHub...
echo [3/3] git add/commit/push>> "%LOG_FILE%"

git -C "%REPO_ROOT%" add -- ^
  paper-monitor/web/papers.json ^
  paper-monitor/web/previous_papers.json ^
  paper-monitor/web/new_papers.json ^
  paper-monitor/web/update_time.json ^
  paper-monitor/web/journal_order.json

if exist "%PROJECT_ROOT%web\latest_email.json" (
    git -C "%REPO_ROOT%" add -- paper-monitor/web/latest_email.json
)

git -C "%REPO_ROOT%" add -A -- "paper-monitor/web/daily_papers_email_*.html"

if errorlevel 1 (
    echo ERROR: git add failed.
    echo ERROR: git add failed.>> "%LOG_FILE%"
    exit /b 1
)

git -C "%REPO_ROOT%" diff --cached --quiet

if not errorlevel 1 (
    echo No changes detected. Skip commit and push.
    echo No changes detected. Skip commit and push.>> "%LOG_FILE%"
    exit /b 0
)

git -C "%REPO_ROOT%" commit -m "Update Paper Monitor"

if errorlevel 1 (
    echo ERROR: git commit failed.
    echo ERROR: git commit failed.>> "%LOG_FILE%"
    exit /b 1
)

git -C "%REPO_ROOT%" push

if errorlevel 1 (
    echo ERROR: git push failed.
    echo ERROR: git push failed.>> "%LOG_FILE%"
    exit /b 1
)

echo Paper Monitor update published successfully.
echo Paper Monitor update published successfully: %date% %time%>> "%LOG_FILE%"

exit /b 0
