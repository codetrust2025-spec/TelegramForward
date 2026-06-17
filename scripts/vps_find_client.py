#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "grep -rn 'TelegramClient\\|get_client\\|session' /opt/telegramforward.old/core/*.py 2>/dev/null | grep -v '.pyc' | head -40",
    "grep -rn 'display_name\\|display-name' /opt/telegramforward.old/static/assets/app-BkUk1ts9.js 2>/dev/null | head -5",
]
for cmd in cmds:
    print("\n===", cmd[:85], "===")
    _, stdout, _ = c.exec_command(cmd, timeout=60)
    out = stdout.read().decode(errors="replace")
    print(out[:5000] if out else "(empty)")
c.close()
