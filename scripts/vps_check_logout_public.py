#!/usr/bin/env python3
import os, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
for cmd in [
    "grep -A6 '_PUBLIC_EXACT' /opt/telegramforward.old/core/dashboard_auth_vps.py | head -10",
    "cd /opt/telegramforward && ./venv/bin/python -c \"from core.dashboard_auth_vps import is_public_path; print(is_public_path('/auth/logout'))\"",
]:
    print('===', cmd)
    _, o, e = c.exec_command(cmd, timeout=30)
    print(o.read().decode())
    print(e.read().decode())
c.close()
