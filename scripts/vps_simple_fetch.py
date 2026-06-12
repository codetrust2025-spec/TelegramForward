#!/usr/bin/env python3
import os, socket, paramiko

PASSWORD = os.environ.get("VPS_PASSWORD", "")

def run(cmd, timeout=180):
    sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
    t = paramiko.Transport(sock)
    t.connect(username="root", password=PASSWORD)
    ch = t.open_session()
    ch.settimeout(timeout)
    ch.exec_command(cmd)
    out = b""
    while True:
        if ch.recv_ready():
            out += ch.recv(65535)
        if ch.exit_status_ready():
            while ch.recv_ready():
                out += ch.recv(65535)
            break
    t.close()
    return out.decode("utf-8", errors="replace")

cmds = [
    "cat /opt/telegramforward.old/data/accounts/account4/groups_health.json | head -c 4000",
    "cat /opt/telegramforward.old/data/accounts/account8/groups_health.json | head -c 4000",
    "ls -la /opt/telegramforward.old/data/accounts/account8/",
    "grep shutdown /opt/telegramforward.old/data/reload.log | tail -20",
    "grep account4 /opt/telegramforward.old/data/reload.log | tail -15",
    "grep account8 /opt/telegramforward.old/data/reload.log | tail -15",
    "wc -l /root/.pm2/logs/telegram-backend-error.log",
    "tail -100 /root/.pm2/logs/telegram-backend-error.log",
    "grep -i account4 /root/.pm2/logs/telegram-backend-error.log | tail -20",
    "grep -i account8 /root/.pm2/logs/telegram-backend-error.log | tail -20",
]
for c in cmds:
    print("=" * 60)
    print("CMD:", c)
    print(run(c))
