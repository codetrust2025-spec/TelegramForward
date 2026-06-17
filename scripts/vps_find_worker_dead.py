#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command("grep -rn 'worker_task_dead' /opt/telegramforward.old/ 2>/dev/null | head -20", timeout=30)
print(stdout.read().decode(errors="replace"))
_, stdout, _ = c.exec_command("grep -rn 'worker_restarts\\|Restarting worker' /opt/telegramforward.old/ 2>/dev/null | head -30", timeout=30)
print("\n=== restarts ===")
print(stdout.read().decode(errors="replace"))
_, stdout, _ = c.exec_command("tail -100 /root/.pm2/logs/telegram-backend-error.log | grep -A5 -i 'account7\\|SyntaxError\\|IndentationError\\|account_worker'", timeout=30)
print("\n=== recent errors ===")
print(stdout.read().decode(errors="replace")[:6000])
c.close()
