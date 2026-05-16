@echo off
echo Starting Telegram Forwarder Dashboard...
echo.

start "Backend - FastAPI" cmd /k "python -m uvicorn server:app --reload --port 8000"
timeout /t 2 /nobreak >nul
start "Frontend - React" cmd /k "cd dashboard && npm run dev"

echo.
echo Backend running at: http://localhost:8000
echo Frontend running at: http://localhost:3000
echo.
echo Open your browser at http://localhost:3000
pause
