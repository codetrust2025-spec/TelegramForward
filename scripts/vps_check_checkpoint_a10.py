#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("cat /opt/telegramforward.old/data/accounts/account10/cycle_checkpoint.json 2>/dev/null; echo; wc -c /opt/telegramforward.old/data/accounts/account10/group_intelligence.json", timeout=30)
print(stdout.read().decode())
c.close()
