#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -rn 'health_score' /opt/telegramforward.old/workers/ /opt/telegramforward.old/core/group_intelligence*.py 2>/dev/null | head -40", timeout=30)
print(stdout.read().decode()[:5000])
c.close()
