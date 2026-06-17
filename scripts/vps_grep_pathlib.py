#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -n 'pathlib\\|cycle_debug\\|CYCLE_DEBUG' /opt/telegramforward.old/workers/account_worker.py", timeout=30)
print(stdout.read().decode(errors="replace"))
_, stdout, _ = c.exec_command("sed -n '2045,2075p' /opt/telegramforward.old/workers/account_worker.py", timeout=30)
print("\n=== except block ===")
print(stdout.read().decode(errors="replace"))
_, stdout, _ = c.exec_command("sed -n '2515,2540p' /opt/telegramforward.old/workers/account_worker.py", timeout=30)
print("\n=== campaign except ===")
print(stdout.read().decode(errors="replace"))
c.close()
