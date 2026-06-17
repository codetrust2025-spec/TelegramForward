#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
local = r"C:\Users\codet\OneDrive\Desktop\Automation\scripts\ai_smart_reply_vps.py"
sftp.get("/opt/telegramforward.old/core/ai_smart_reply.py", local)
sftp.close()
c.close()
print("downloaded", local)
