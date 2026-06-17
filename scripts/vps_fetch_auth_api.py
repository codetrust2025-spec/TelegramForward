#!/usr/bin/env python3
import os
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)
_, stdout, _ = c.exec_command("cat /opt/telegramforward.old/core/dashboard_auth_api.py", timeout=30)
print(stdout.read().decode())
c.close()
