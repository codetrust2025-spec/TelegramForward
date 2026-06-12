#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

cmds = [
    "tail -200 /root/.pm2/logs/telegram-backend-error.log",
    "ls -la /opt/telegramforward.old/data/logs/ 2>/dev/null | head -20",
    "find /opt/telegramforward.old/data -name '*account7*' -type f 2>/dev/null | head -20",
    "pm2 logs telegram-backend --lines 100 --nostream 2>&1 | tail -100",
    "curl -s http://127.0.0.1:8000/health 2>/dev/null; echo; curl -s http://127.0.0.1:8000/api/status 2>/dev/null | head -c 2000",
]
for cmd in cmds:
    print(f"\n{'='*60}\n$ {cmd}\n{'='*60}")
    _, stdout, stderr = c.exec_command(cmd, timeout=90)
    print(stdout.read().decode(errors="replace")[:12000])
    err = stderr.read().decode(errors="replace")
    if err.strip():
        print("STDERR:", err[:2000])
c.close()
