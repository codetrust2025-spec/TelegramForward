#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmds = [
    "grep -n 'MESSAGE_FILE\\|DEFAULT_MESSAGE\\|STATE_DIR' /opt/telegramforward.old/core/config.py | head -20",
    "grep -rn '@.*message\\|/message' /opt/telegramforward.old/server.py /opt/telegramforward.old/routes 2>/dev/null | head -25",
]
for cmd in cmds:
    print("===", cmd[:70])
    _, stdout, _ = c.exec_command(cmd, timeout=30)
    print(stdout.read().decode("utf-8", errors="replace"))
c.close()
