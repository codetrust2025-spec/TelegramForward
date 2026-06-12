#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "grep -rn 'UpdateProfile\\|edit_profile\\|profile_name\\|set_name\\|first_name.*last_name' /opt/telegramforward.old 2>/dev/null | grep -v '.pyc\\|node_modules\\|dm_inbox' | head -60",
    "grep -rn 'display-name\\|display_name\\|onRenamed' /opt/telegramforward.old/static 2>/dev/null | head -20",
]
for cmd in cmds:
    print("\n===", cmd[:80], "===")
    _, stdout, _ = c.exec_command(cmd, timeout=60)
    print(stdout.read().decode(errors="replace")[:10000])
c.close()
