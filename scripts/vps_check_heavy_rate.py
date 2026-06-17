#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -n 'heavy_rate_limit' /opt/telegramforward.old/workers/account_state.py /opt/telegramforward.old/workers/feature_runtime.py /opt/telegramforward.old/workers/account_worker.py | head -50", timeout=30)
print(stdout.read().decode(errors="replace"))
_, stdout, _ = c.exec_command("grep -n 'campaign_' /opt/telegramforward.old/workers/account_state.py | head -60", timeout=30)
print("\n=== campaign_ fields ===")
print(stdout.read().decode(errors="replace"))
c.close()
