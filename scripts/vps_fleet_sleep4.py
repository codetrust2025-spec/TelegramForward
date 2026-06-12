#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

cmds = [
    "grep -rn 'minCountdown\\|sleepingCount\\|fleet' /opt/telegramforward.old --include='*.py' 2>/dev/null | head -50",
    "grep -rn 'next_cycle_in' /opt/telegramforward.old --include='*.py' 2>/dev/null | head -30",
    "sed -n '1,80p' /opt/telegramforward.old/core/posting_mode.py",
]
for cmd in cmds:
    print("=== CMD ===")
    _, stdout, _ = c.exec_command(cmd, timeout=90)
    print(stdout.read().decode("utf-8", errors="replace"))
c.close()
