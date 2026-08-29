@echo off
echo =======================================================
echo Launching EventLens AI Full Stack Application...
echo =======================================================
start "EventLens Backend (Port 8000)" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --reload --port 8000"
start "EventLens Frontend (Port 3000)" cmd /k "cd /d %~dp0frontend && npm run dev"
echo.
echo Servers are launching in separate windows:
echo - Frontend: http://localhost:3000
echo - Backend API & Docs: http://localhost:8000/docs
echo.
pause
