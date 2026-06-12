#!/usr/bin/env python3
import os, socket, paramiko, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

cmds = [
    "find /opt/telegramforward.old/data/accounts -name 'message.txt' 2>/dev/null | head -15",
    "grep -rl 'Power BI\\|9032388581\\|100+ placed\\|MERN' /opt/telegramforward.old/data /opt/telegramforward.old/core 2>/dev/null | head -20",
    "for f in /opt/telegramforward.old/data/accounts/account*/message.txt; do [ -f \"$f\" ] && echo \"=== $f ===\" && head -40 \"$f\"; done 2>/dev/null | head -200",
]
for cmd in cmds:
    print("\n--- CMD:", cmd[:80], "---")
    _, stdout, stderr = c.exec_command(cmd, timeout=60)
    print(stdout.read().decode(errors="replace"))
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("ERR:", err)
c.close()
