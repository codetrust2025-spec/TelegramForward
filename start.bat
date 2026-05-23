@echo off
title TelegramForward
cd /d "%~dp0"

echo.
echo  TelegramForward - starting (one server only)
echo  -------------------------------------------
echo  URL: http://127.0.0.1:8000
echo.

REM Stop duplicate servers that cause "database is locked" and connection errors
echo  Stopping old servers on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr LISTENING') do (
  taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo  Starting keep-alive...
python scripts\keep_alive.py

echo.
echo  Server stopped.
pause
