#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "ls /opt/telegramforward.old/data/accounts/",
    "grep -rn 'display_name\\|UpdateProfile\\|rename' /opt/telegramforward.old/core/*.py /opt/telegramforward.old/*.py 2>/dev/null | head -50",
]
for cmd in cmds:
    print("---", cmd)
    _, stdout, stderr = c.exec_command(cmd, timeout=60)
    print(stdout.read().decode(errors="replace"))
c.close()
