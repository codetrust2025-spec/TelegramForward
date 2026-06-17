#!/usr/bin/env python3
import os, socket, sys, json
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

def run(cmd, timeout=60):
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    _, o, e = c.exec_command(cmd, timeout=timeout)
    return o.read().decode() + e.read().decode()

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=== health ===")
    print(run("curl -s --max-time 8 http://127.0.0.1:8000/health"))
    print("\n=== posting modes ===")
    print(run("ls /opt/telegramforward.old/data/accounts/account1/*.json 2>/dev/null | head -5"))
    print(run("cat /opt/telegramforward.old/data/posting_modes.json 2>/dev/null | head -c 600"))
    print("\n=== fleet start flags ===")
    print(run("grep -r 'running\\|forwarding_enabled' /opt/telegramforward.old/data/accounts/account1/posting_mode.json 2>/dev/null; cat /opt/telegramforward.old/data/accounts/account1/posting_mode.json 2>/dev/null | head -c 500"))
    print("\n=== pm2 describe telegram-backend (last lines) ===")
    print(run("pm2 logs telegram-backend --lines 20 --nostream 2>&1 | tail -20"))
