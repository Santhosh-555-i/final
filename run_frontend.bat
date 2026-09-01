@echo off
echo =======================================================
echo Starting EventLens AI Frontend (Next.js on Port 3000)...
echo =======================================================
cd /d "%~dp0frontend"
npm run dev
pause
