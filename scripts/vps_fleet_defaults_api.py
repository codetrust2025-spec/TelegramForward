#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

cmds = [
    "grep -n 'fleet/defaults\\|apply.*message\\|campaign_message' /opt/telegramforward.old/server.py | head -40",
    "grep -rn 'fleet/defaults\\|apply.*campaign\\|campaign_message' /opt/telegramforward.old --include='*.py' | head -30",
]
for cmd in cmds:
    print("===", cmd[:75])
    _, stdout, _ = c.exec_command(cmd, timeout=60)
    print(stdout.read().decode("utf-8", errors="replace")[:6000])
c.close()
