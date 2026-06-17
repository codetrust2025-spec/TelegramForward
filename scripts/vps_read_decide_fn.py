#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -n 'def decide' /opt/telegramforward.old/core/unified_scheduler.py", timeout=30)
print(stdout.read().decode())
_, stdout, _ = c.exec_command("sed -n '218,270p' /opt/telegramforward.old/core/unified_scheduler.py", timeout=30)
print(stdout.read().decode())
c.close()
