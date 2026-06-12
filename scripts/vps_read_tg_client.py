#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -n 'def get_client\\|UpdateProfile\\|async def' /opt/telegramforward.old/core/telegram_client.py | head -40", timeout=30)
print(stdout.read().decode(errors="replace"))
_, stdout, _ = c.exec_command("sed -n '1,80p' /opt/telegramforward.old/core/telegram_client.py", timeout=30)
print(stdout.read().decode(errors="replace"))
c.close()
