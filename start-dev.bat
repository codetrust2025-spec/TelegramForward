@echo off
title TelegramForward DEV
cd /d "%~dp0"
echo DEV mode: UI http://127.0.0.1:3000  API http://127.0.0.1:8000
echo Keep this window open. For daily use, double-click START.bat instead.
python run.py
pause
