#!/usr/bin/env python3
import os, socket, sys
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
cmds = [
    "head -80 /opt/telegramforward.old/core/dashboard_auth.py 2>/dev/null || head -80 /opt/telegramforward.old/dashboard_auth.py",
    "grep -n 'feature=campaign\\|start_account' /opt/telegramforward.old/server.py | head -15",
    "tail -50 /root/.pm2/logs/telegram-backend-error.log | grep -iE 'account3|account8|error|Attribute|Traceback' | tail -25",
]
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
for cmd in cmds:
    print(f"\n=== {cmd[:55]} ===")
    _, stdout, _ = c.exec_command(cmd, timeout=25)
    print(stdout.read().decode("utf-8", errors="replace")[:3500])
c.close()
