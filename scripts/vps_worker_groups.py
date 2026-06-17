#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
cmds = [
    "sed -n '1670,1740p' /opt/telegramforward.old/workers/account_worker.py",
    "grep -rn 'refresh.joined\\|refresh_joined\\|JoinedMembership\\|load.*groups' /opt/telegramforward.old/core /opt/telegramforward.old/server.py 2>/dev/null | head -25",
    "grep -rn 'SEND_FAIL\\|appledeveloper' /opt/telegramforward.old --include='*.py' | head -15",
    "tail -80 /root/.pm2/logs/telegram-backend-out.log | grep -iE 'account[0-9]|error|fail|group|join|recover' || tail -40 /root/.pm2/logs/telegram-backend-out.log",
]
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
for cmd in cmds:
    print("===", cmd[:70])
    _, stdout, _ = c.exec_command(cmd, timeout=60)
    print(stdout.read().decode("utf-8", errors="replace")[:8000])
    print()
c.close()
