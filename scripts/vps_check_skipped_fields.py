#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -n 'skipped' /opt/telegramforward.old/workers/account_state.py", timeout=30)
print(stdout.read().decode())
_, stdout, _ = c.exec_command("cd /opt/telegramforward.old && ./venv/bin/python3 -c \"from workers.account_state import AccountState; a=AccountState('x'); a.skipped_other=5; print('ok', a.skipped_other)\" 2>&1", timeout=30)
print("test:", stdout.read().decode())
c.close()
