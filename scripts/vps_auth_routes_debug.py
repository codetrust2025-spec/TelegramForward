#!/usr/bin/env python3
import os
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)
cmds = [
    "pm2 describe telegram-backend 2>/dev/null | head -30",
    "grep -rn 'dashboard_auth' /opt/telegramforward.old/server.py /opt/telegramforward.old/core/*.py 2>/dev/null | head -30",
    "curl -s http://127.0.0.1:8000/health",
    "grep -n 'auth/status\\|register.*auth\\|mount.*auth' /opt/telegramforward.old/server.py | head -20",
    "ls -la /opt/telegramforward.old/core/dashboard_auth*.py",
    "curl -s -X POST http://127.0.0.1:8000/auth/login -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"test\"}'",
]
for cmd in cmds:
    print(f"\n=== {cmd} ===")
    _, stdout, stderr = c.exec_command(cmd, timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    print(out[:4000])
    if err.strip():
        print("stderr:", err[:500])
c.close()
