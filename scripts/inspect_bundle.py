#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
BUNDLE = "/opt/telegramforward.old/static/assets/app-D89Ign3q.js"

sock = socket.create_connection((HOST, 22), timeout=30)
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
sftp = c.open_sftp()
with sftp.open(BUNDLE, "r") as f: b = f.read().decode("utf-8", errors="replace")
sftp.close(); c.close()

i = b.find("cand-page-topbar")
print(b[i:i+2000])
print("\n--- toolbar ---")
j = b.find('className:"cand-toolbar"')
print(b[j:j+600])
