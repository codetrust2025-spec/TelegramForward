#!/usr/bin/env python3
import os, socket, sys
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("cat /opt/telegramforward.old/core/dashboard_auth_vps.py", timeout=20)
print(stdout.read().decode()[:4000])
c.close()
