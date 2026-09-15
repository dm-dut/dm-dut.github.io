@echo off
chcp 65001 >nul
setlocal EnableExtensions

echo ==================================================
echo Paper Monitor Update, Email Generation and Git Push
echo ==================================================

REM Current BAT folder:
REM   dm-dut.github.io\paper-monitor\
REM Git repository root:
REM   dm-dut.github.io\
REM
REM Workflow:
REM   1. Pull latest GitHub changes
REM   2. Run update.py
REM   3. Run generate_email.py locally
REM   4. Stage generated JSON / DB / logs / email files
REM   5. Commit
REM   6. Push to GitHub
REM   7. GitHub Actions sends the email when
REM      paper-monitor/web/latest_email.json changes
REM ==================================================

cd /d "%~dp0"

set "PROJECT_ROOT=%~dp0"
for %%I in ("%PROJECT_ROOT%..") do set "REPO_ROOT=%%~fI"

REM If Task Scheduler cannot find Python, replace "python"
REM with the full path to python.exe.
set "PYTHON_EXE=python"

echo.
echo Project root:
echo %PROJECT_ROOT%
echo Repository root:
echo %REPO_ROOT%

REM ==================================================
REM [1/7] Pull latest remote changes
REM ==================================================

echo.
echo [1/7] Pulling latest changes from GitHub...

git -C "%REPO_ROOT%" pull --rebase --autostash

IF ERRORLEVEL 1 (
    echo.
    echo ERROR: Initial git pull failed.
    echo Update cancelled to avoid working on an outdated repository.
    echo Please check network connection, Git credentials, or merge conflicts.
    pause
    exit /b 1
)

REM ==================================================
REM [2/7] Update local paper database and JSON
REM ==================================================

echo.
echo [2/7] Updating paper database...

"%PYTHON_EXE%" scripts\update.py

IF ERRORLEVEL 1 (
    echo.
    echo ERROR: update.py failed.
    echo Email generation, commit and push cancelled.
    pause
    exit /b 1
)

REM ==================================================
REM [3/7] Generate email HTML locally
REM ==================================================

echo.
echo [3/7] Generating email HTML locally...

"%PYTHON_EXE%" scripts\generate_email.py

IF ERRORLEVEL 1 (
    echo.
    echo ERROR: generate_email.py failed.
    echo Git commit and push cancelled.
    pause
    exit /b 1
)

REM ==================================================
REM [4/7] Check repository status
REM ==================================================

echo.
echo [4/7] Checking git status...

git -C "%REPO_ROOT%" status

REM ==================================================
REM [5/7] Stage generated files
REM ==================================================

echo.
echo [5/7] Adding updated files...

git -C "%REPO_ROOT%" add -- ^
    paper-monitor/web/papers.json ^
    paper-monitor/web/new_papers.json ^
    paper-monitor/web/previous_papers.json ^
    paper-monitor/web/update_time.json ^
    paper-monitor/web/journal_order.json ^
    paper-monitor/database/papers.db ^
    paper-monitor/logs/

IF ERRORLEVEL 1 (
    echo.
    echo ERROR: git add failed for data files.
    pause
    exit /b 1
)

if exist "%PROJECT_ROOT%web\latest_email.json" (
    git -C "%REPO_ROOT%" add -- paper-monitor/web/latest_email.json

    IF ERRORLEVEL 1 (
        echo.
        echo ERROR: git add failed for latest_email.json.
        pause
        exit /b 1
    )
)

if exist "%PROJECT_ROOT%web\daily_papers_email_*.html" (
    git -C "%REPO_ROOT%" add -A -- "paper-monitor/web/daily_papers_email_*.html"

    IF ERRORLEVEL 1 (
        echo.
        echo ERROR: git add failed for email HTML files.
        pause
        exit /b 1
    )
)

REM ==================================================
REM [6/7] Commit staged changes if needed
REM ==================================================

echo.
echo [6/7] Checking staged changes...

git -C "%REPO_ROOT%" diff --cached --quiet

IF ERRORLEVEL 1 (
    echo Changes detected. Creating commit...

    git -C "%REPO_ROOT%" commit -m "Update Paper Monitor %date% %time%"

    IF ERRORLEVEL 1 (
        echo.
        echo ERROR: git commit failed.
        pause
        exit /b 1
    )
) ELSE (
    echo No new staged changes to commit.
    echo A push will still be attempted in case a previous local commit was not pushed.
)

REM ==================================================
REM [7/7] Push to GitHub with automatic recovery
REM ==================================================

echo.
echo [7/7] Pushing to GitHub...

git -C "%REPO_ROOT%" push

IF NOT ERRORLEVEL 1 (
    goto PUSH_SUCCESS
)

echo.
echo First git push failed.
echo Pulling latest remote changes and retrying...

git -C "%REPO_ROOT%" pull --rebase --autostash

IF ERRORLEVEL 1 (
    echo.
    echo Recovery pull failed.
    echo Waiting 10 seconds and trying the pull one more time...
    timeout /t 10 /nobreak >nul

    git -C "%REPO_ROOT%" pull --rebase --autostash

    IF ERRORLEVEL 1 (
        echo.
        echo ERROR: Recovery pull failed twice.
        echo Please check:
        echo   1. Internet connection
        echo   2. GitHub credentials
        echo   3. Merge/rebase conflicts
        echo.
        echo Current git status:
        git -C "%REPO_ROOT%" status
        pause
        exit /b 1
    )
)

echo.
echo Retrying git push...

git -C "%REPO_ROOT%" push

IF NOT ERRORLEVEL 1 (
    goto PUSH_SUCCESS
)

echo.
echo Second git push failed.
echo Waiting 10 seconds before the final retry...

timeout /t 10 /nobreak >nul

git -C "%REPO_ROOT%" push

IF ERRORLEVEL 1 (
    echo.
    echo ERROR: Git push failed after all retry attempts.
    echo.
    echo Current git status:
    git -C "%REPO_ROOT%" status
    echo.
    echo The local commit has NOT been deleted.
    echo You can retry "git push" later without running update.py again.
    pause
    exit /b 1
)

:PUSH_SUCCESS

echo.
echo ==================================================
echo Paper Monitor update completed successfully.
echo Local email HTML generated when new papers exist.
echo Generated files pushed to GitHub.
echo GitHub Actions will send the email when
echo latest_email.json has changed.
echo ==================================================

pause
exit /b 0
