#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -rn 'suspend\\|pause_all\\|quiesce\\|membership' /opt/telegramforward.old/server.py /opt/telegramforward.old/services/dm_inbox_service.py 2>/dev/null | head -20", timeout=30)
print(stdout.read().decode())
_, stdout, _ = c.exec_command("grep -n 'def campaign_runtime' /opt/telegramforward.old/workers/*.py", timeout=30)
print("campaign_runtime:", stdout.read().decode())
_, stdout, _ = c.exec_command("sed -n '1,80p' /opt/telegramforward.old/workers/account_state.py", timeout=30)
print(stdout.read().decode())
c.close()
