#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
BUNDLE = "/opt/telegramforward.old/static/assets/app-D89Ign3q.js"

sock = socket.create_connection((HOST, 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
sftp = c.open_sftp()
with sftp.open(BUNDLE, "r") as f:
    b = f.read().decode("utf-8", errors="replace")
sftp.close()
c.close()

for pat in ["workspaceMode", "hideAccountsModeFilter", "accountsModeFilter", "Log in", "login", "compactSetup", "showShutdown"]:
    idx = 0
    hits = []
    while True:
        i = b.find(pat, idx)
        if i < 0:
            break
        hits.append(i)
        idx = i + 1
        if len(hits) >= 8:
            break
    print(f"\n=== {pat} ({len(hits)} hits) ===")
    for i in hits[:5]:
        print(f"  @{i}: {b[max(0,i-40):i+120].replace(chr(10),' ')}")

# find fy( calls
import re
for m in re.finditer(r'fy,\{', b):
    print(f"\nfy component @{m.start()}: {b[m.start():m.start()+500]}")
    break

for m in re.finditer(r'accountsModeFilter:', b):
    print(f"\naccountsModeFilter @{m.start()}: {b[m.start()-80:m.start()+200]}")
    if m.start() > 550000:
        break
