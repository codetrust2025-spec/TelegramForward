#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
files = [
    "/opt/telegramforward.old/data/message.txt",
    "/opt/telegramforward.old/data/custom_message.txt",
    "/opt/telegramforward.old/data/accounts/account6/message.txt",
]
for f in files:
    print("\n" + "="*60)
    print(f)
    print("="*60)
    _, stdout, _ = c.exec_command(f"cat {f} 2>/dev/null", timeout=30)
    print(stdout.read().decode(errors="replace"))
c.close()
