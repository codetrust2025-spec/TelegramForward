#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
BUNDLE = "/opt/telegramforward.old/static/assets/app-D89Ign3q.js"
OUT = r"C:\Users\codet\OneDrive\Desktop\Automation\scripts\app_bundle_login_tab.js"

sock = socket.create_connection((HOST, 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
sftp = c.open_sftp()
with sftp.open(BUNDLE, "r") as f:
    b = f.read().decode("utf-8", errors="replace")
sftp.close()
c.close()

# Login tab area
for start in [995500, 1004500, 956000]:
    chunk = b[start:start+3500]
    open(OUT, "a", encoding="utf-8").write(f"\n\n/* ===== @ {start} ===== */\n{chunk}")

print(f"Wrote snippets to {OUT}")
