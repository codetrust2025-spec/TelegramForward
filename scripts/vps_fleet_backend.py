#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

cmds = [
    "grep -n 'def ' /opt/telegramforward.old/services/account_manager.py | head -40",
    "grep -n 'SLEEPING\\|next_cycle_in\\|lifecycle' /opt/telegramforward.old/services/account_manager.py | head -30",
    "grep -n 'pick_forward_rest\\|forward_rest\\|next_cycle' /opt/telegramforward.old/workers/account_worker.py | head -25",
]
for cmd in cmds:
    print("===", cmd)
    _, stdout, _ = c.exec_command(cmd, timeout=60)
    print(stdout.read().decode("utf-8", errors="replace"))
c.close()
