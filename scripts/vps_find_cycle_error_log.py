#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "grep -i 'Cycle error\\|Unexpected error\\|account7.*error' /root/.pm2/logs/telegram-backend-out.log | tail -30",
    "grep -i 'Cycle error\\|Unexpected error' /opt/telegramforward.old/data/logs/*.log 2>/dev/null | tail -20",
    "grep -rn 'def _log' /opt/telegramforward.old/workers/account_worker.py | head -5",
]
for cmd in cmds:
    print(f"\n=== {cmd[:60]} ===")
    _, stdout, _ = c.exec_command(cmd, timeout=30)
    print(stdout.read().decode(errors="replace")[:4000] or "(empty)")
_, stdout, _ = c.exec_command("sed -n '530,580p' /opt/telegramforward.old/workers/account_worker.py", timeout=30)
print("\n=== _log method ===")
print(stdout.read().decode(errors="replace"))
c.close()
