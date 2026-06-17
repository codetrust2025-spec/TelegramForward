#!/usr/bin/env python3
import os, socket, sys
import paramiko
HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection((HOST, 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, sock=sock)
for cmd in [
    "find /opt/telegramforward.old -maxdepth 2 -name '*.session' 2>/dev/null | head -15",
    "grep -iE 'wrong session|Connection failed|Worker started|Cycle started|forwarding loop' /root/.pm2/logs/telegram-backend-error.log 2>/dev/null | tail -25",
    "grep -iE 'wrong session|Connection failed|Worker started|Cycle started' /root/.pm2/logs/telegram-backend-out.log 2>/dev/null | tail -15",
    "ls -la /opt/telegramforward.old/session_account*.session 2>/dev/null | head -12",
]:
    _, o, _ = c.exec_command(cmd, timeout=30)
    print("===", cmd[:60], "===")
    print(o.read().decode())
c.close()
