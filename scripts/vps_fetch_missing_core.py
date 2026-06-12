#!/usr/bin/env python3
import os, socket, sys
from pathlib import Path
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
LOCAL = Path(r"C:\Users\codet\TelegramForward")
files = [
    "core/posting_mode.py",
    "services/account_runtime.py",
    "core/dashboard_auth_vps.py",
]
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
for rel in files:
    local = LOCAL / rel
    local.parent.mkdir(parents=True, exist_ok=True)
    try:
        sftp.get(f"{REMOTE}/{rel}", str(local))
        print("OK", rel)
    except Exception as e:
        print("SKIP", rel, e)
sftp.close()
c.close()
