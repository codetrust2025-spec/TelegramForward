#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, stderr = c.exec_command("cd /opt/telegramforward.old && ./venv/bin/python3 -m py_compile workers/account_worker.py 2>&1", timeout=30)
print("compile:", stdout.read().decode(), stderr.read().decode())
_, stdout, _ = c.exec_command("sed -n '2043,2075p' /opt/telegramforward.old/workers/account_worker.py", timeout=30)
print(stdout.read().decode(errors="replace"))
c.close()
