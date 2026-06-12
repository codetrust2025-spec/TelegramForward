#!/usr/bin/env python3
import os, socket, sys
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
cmds = [
    "tail -5 /opt/telegramforward.old/data/reload.log",
    "tail -30 /root/.pm2/logs/telegram-backend-out.log",
    "tail -20 /root/.pm2/logs/telegram-backend-error.log",
    f"ls /opt/telegramforward.old/data/accounts/account3/account_info.json /opt/telegramforward.old/session_account3.session 2>&1",
]
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
for cmd in cmds:
    print(f"\n=== {cmd[:55]} ===")
    _, stdout, _ = c.exec_command(cmd, timeout=20)
    print(stdout.read().decode("utf-8", errors="replace")[:3000])
c.close()
