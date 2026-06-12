#!/usr/bin/env python3
import os
import socket
import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

sock = socket.create_connection((HOST, 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PASSWORD, sock=sock)

cmds = [
    "cat /opt/telegramforward.old/static/index.html",
    "grep -l fleetDisplaySuccessRate /opt/telegramforward.old/static/assets/*.js",
    "grep should_continue_campaign /opt/telegramforward.old/workers/feature_runtime.py | head -3",
    "pm2 jlist | python3 -c \"import sys,json; d=json.load(sys.stdin); print(d[0]['name'], d[0]['pm2_env']['status'])\"",
]
for cmd in cmds:
    print(">", cmd[:80])
    _, out, err = c.exec_command(cmd, timeout=30)
    print(out.read().decode().strip() or err.read().decode().strip())
    print()

c.close()
