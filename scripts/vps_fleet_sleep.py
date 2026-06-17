#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "grep -rn 'Fleet sleeping\\|minCountdown\\|globalCountdown\\|forward_rest\\|FORWARD_REST' /opt/telegramforward.old/core /opt/telegramforward.old/static/assets/app-BkUk1ts9.js 2>/dev/null | head -30",
    "grep -E 'FORWARD_REST|FORWARD_INTERVAL' /opt/telegramforward.old/.env /opt/telegramforward.old/core/posting_mode.py 2>/dev/null",
]
for cmd in cmds:
    print("\n---", cmd[:80])
    _, stdout, _ = c.exec_command(cmd, timeout=30)
    print(stdout.read().decode(errors="replace")[:5000])
c.close()
