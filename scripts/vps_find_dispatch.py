#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -n 'def dispatch_inline\\|GROUP_POST' /opt/telegramforward.old/**/*.py 2>/dev/null | head -15; grep -rn 'def dispatch_inline' /opt/telegramforward.old/ 2>/dev/null | head -5", timeout=30)
print(stdout.read().decode()[:2000])
c.close()
