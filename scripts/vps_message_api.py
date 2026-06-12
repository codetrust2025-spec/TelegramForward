#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("sed -n '1410,1460p' /opt/telegramforward.old/server.py", timeout=30)
print(stdout.read().decode("utf-8", errors="replace"))
_, stdout, _ = c.exec_command("sed -n '305,330p' /opt/telegramforward.old/core/config.py", timeout=30)
print("=== DEFAULT_MESSAGE ===")
print(stdout.read().decode("utf-8", errors="replace")[:800])
c.close()
