#!/usr/bin/env python3
import os, socket, sys
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
cmds = [
    "grep -n 'resume_persisted' -A 40 /opt/telegramforward.old/services/account_manager.py | head -50",
    "grep 'Auto-resumed\\|resume\\|running_workers' /opt/telegramforward.old/data/reload.log | tail -15",
    "grep -i 'resume\\|account3\\|startup' /root/.pm2/logs/telegram-backend-out.log | tail -20",
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
