#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
BUNDLE = "/opt/telegramforward.old/static/assets/app-D89Ign3q.js"
LOCAL = r"C:\Users\codet\OneDrive\Desktop\Automation\static\assets\app-D89Ign3q.js"

sock = socket.create_connection((HOST, 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
sftp = c.open_sftp()
os.makedirs(os.path.dirname(LOCAL), exist_ok=True)
sftp.get(BUNDLE, LOCAL)
sftp.close()
c.close()
print(f"Downloaded {os.path.getsize(LOCAL)} bytes to {LOCAL}")

# find Zh and Wi
b = open(LOCAL, encoding="utf-8").read()
for fn in ["function Zh(", "function Wi(", "function C0(", "function Gl("]:
    i = b.find(fn)
    print(f"\n{fn} @ {i}")
    if i >= 0:
        print(b[i:i+400])
