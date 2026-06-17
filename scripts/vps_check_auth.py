#!/usr/bin/env python3
import os, socket, sys
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
cmds = [
    f"grep -E '^DASHBOARD_' {REMOTE}/.env | sed 's/=.*/=***/'",
    f"grep -n 'start_account\\|Authentication' {REMOTE}/server.py | head -20",
    f"grep -n 'auto.resume\\|running_workers' {REMOTE}/services/account_manager.py | head -15",
]
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
for cmd in cmds:
    print(f"\n=== {cmd[:60]} ===")
    _, stdout, _ = c.exec_command(cmd, timeout=20)
    print(stdout.read().decode()[:2000])
c.close()
