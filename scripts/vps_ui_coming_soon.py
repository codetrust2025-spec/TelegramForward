#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -rn 'coming soon\\|not wired\\|optional\\|future:' /opt/telegramforward.old/dashboard /opt/telegramforward.old/static 2>/dev/null | grep -v node_modules | head -15", timeout=30)
print(stdout.read().decode()[:2000] or "(none)")
_, stdout, _ = c.exec_command("ls /opt/telegramforward.old/docs/; grep -l 'Status\\|Done\\|Pending' /opt/telegramforward.old/docs/*.md", timeout=30)
print(stdout.read().decode())
c.close()
