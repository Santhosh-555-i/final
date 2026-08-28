@echo off
start cmd /k "cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
start cmd /k "cd frontend && npm run dev"
timeout /t 3 /nobreak >nul
start http://localhost:3000
