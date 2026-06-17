#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
for start, end, label in [(1555, 1620, "cycle_start"), (2040, 2075, "cycle_end"), (2485, 2550, "campaign_loop")]:
    _, stdout, _ = c.exec_command(f"sed -n '{start},{end}p' /opt/telegramforward.old/workers/account_worker.py", timeout=30)
    print(f"\n=== {label} {start}-{end} ===")
    print(stdout.read().decode(errors="replace"))
c.close()
