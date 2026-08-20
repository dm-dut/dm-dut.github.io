@echo off
chcp 65001 >nul

echo ==================================================
echo Paper Monitor Update and Git Push
echo ==================================================

REM Change to project root
cd /d %~dp0

echo.
echo [1/4] Updating paper database...
python scripts\update.py

IF ERRORLEVEL 1 (
    echo.
    echo Update failed. Git push cancelled.
    pause
    exit /b 1
)

echo.
echo [2/4] Checking git status...
git status

echo.
echo [3/4] Adding updated files...
git add web\papers.json web\new_papers.json web\previous_papers.json web\update_time.json database\papers.db logs\

echo.
echo [4/4] Commit and push...

git commit -m "Update paper monitor data %date% %time%"

IF ERRORLEVEL 1 (
    echo No changes to commit.
)

git push

IF ERRORLEVEL 1 (
    echo.
    echo Git push failed.
    pause
    exit /b 1
)

echo.
echo ==================================================
echo Update completed successfully.
echo ==================================================

pause
