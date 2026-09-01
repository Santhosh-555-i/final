@echo off
echo =======================================================
echo Starting EventLens AI Backend (FastAPI on Port 8000)...
echo =======================================================
cd /d "%~dp0backend"
python -m uvicorn app.main:app --reload --port 8000
pause
