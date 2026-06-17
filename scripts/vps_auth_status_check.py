#!/usr/bin/env python3
import os
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)
for cmd in [
    "grep DASHBOARD /opt/telegramforward.old/.env | sed 's/=.*/=***/'",
    "curl -s http://127.0.0.1:8000/auth/status",
    "curl -s -X POST http://127.0.0.1:8000/auth/logout -c /tmp/t.txt -b /tmp/t.txt",
    "curl -s http://127.0.0.1:8000/auth/status -b /tmp/t.txt",
]:
    print(f"\n=== {cmd} ===")
    _, stdout, stderr = c.exec_command(cmd, timeout=30)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err.strip():
        print("stderr:", err)
c.close()
