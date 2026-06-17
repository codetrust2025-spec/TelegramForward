#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -E \"Error on:|has no attribute 'success'|Message sent to\" /root/.pm2/logs/telegram-backend-out.log 2>/dev/null | tail -20", timeout=30)
print(stdout.read().decode() or "(none in out log)")
_, stdout, _ = c.exec_command("grep -E \"Error on:|has no attribute 'success'|Message sent\" /opt/telegramforward.old/data/reload.log 2>/dev/null | tail -10", timeout=30)
print("\nreload:", stdout.read().decode()[:2000] or "(none)")
c.close()
