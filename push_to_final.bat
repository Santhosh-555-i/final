@echo off
echo =======================================================
echo Pushing EventLens AI to https://github.com/Santhosh-555-i/final.git
echo =======================================================
git remote set-url origin https://github.com/Santhosh-555-i/final.git
git add .
git commit -m "feat: complete EventLens AI full stack application"
git push -u origin main
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo If push was rejected due to existing files on remote, forcing update...
    git push -u origin main --force
)
echo.
echo Done!
pause
