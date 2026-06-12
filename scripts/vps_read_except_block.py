#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("sed -n '1980,2080p' /opt/telegramforward.old/workers/account_worker.py", timeout=30)
print(stdout.read().decode())
_, stdout, _ = c.exec_command("cat /opt/telegramforward.old/workers/feature_runtime.py", timeout=30)
print("=== feature_runtime ===")
print(stdout.read().decode()[:4000])
c.close()
