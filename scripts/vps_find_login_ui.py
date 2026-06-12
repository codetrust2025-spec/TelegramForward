#!/usr/bin/env python3
import os, socket, paramiko, re

PASSWORD = os.environ.get("VPS_PASSWORD", "")

def run(cmd, timeout=120):
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

print(run("ls -la /opt/telegramforward.old/static/assets/*.js"))
for pat in ["campaign", "Shared link", "Shutdown tab", "Defaults"]:
    print(f"\n=== grep {pat} ===")
    print(run(f"grep -o '.{{0,60}}{pat}.{{0,60}}' /opt/telegramforward.old/static/assets/*.js 2>/dev/null | head -3"))
