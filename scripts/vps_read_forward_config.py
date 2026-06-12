#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("sed -n '302,420p' /opt/telegramforward.old/core/posting_mode.py", timeout=30)
print(stdout.read().decode())
_, stdout, _ = c.exec_command("grep -rn 'set_forward\\|forward_source\\|source_peer' /opt/telegramforward.old/core/posting_mode.py /opt/telegramforward.old/server.py | head -25", timeout=30)
print(stdout.read().decode())
c.close()
