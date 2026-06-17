#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -rn 'Worker stopped\\|worker_stopped\\|110 / 110\\|groups this tick' /opt/telegramforward.old/static/ 2>/dev/null | head -10; grep -rn 'tick_progress\\|campaign_tick' /opt/telegramforward.old/ 2>/dev/null | head -15", timeout=30)
print(stdout.read().decode()[:3000])
c.close()
