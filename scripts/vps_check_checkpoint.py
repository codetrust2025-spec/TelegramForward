#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "sed -n '380,430p' /opt/telegramforward.old/workers/account_worker.py",
    "find /opt/telegramforward.old/data/accounts/account7 -type f 2>/dev/null | head -30",
    "cat /opt/telegramforward.old/data/accounts/account7/cycle_checkpoint.json 2>/dev/null || echo no checkpoint",
    "grep -r 'should_continue' /opt/telegramforward.old/workers/account_state.py | head -10",
]
for cmd in cmds:
    print(f"\n=== {cmd[:70]} ===")
    _, stdout, _ = c.exec_command(cmd, timeout=30)
    print(stdout.read().decode(errors="replace")[:3000])
c.close()
