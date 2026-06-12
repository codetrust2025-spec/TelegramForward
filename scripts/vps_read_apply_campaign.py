#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("sed -n '70,120p' /opt/telegramforward.old/services/fleet_setup_service.py", timeout=30)
print(stdout.read().decode("utf-8", errors="replace"))
_, stdout, _ = c.exec_command("sed -n '1340,1400p' /opt/telegramforward.old/server.py", timeout=30)
print("=== server ===")
print(stdout.read().decode("utf-8", errors="replace"))
c.close()
