#!/usr/bin/env python3
import os, socket, paramiko, re, sys
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

out = []
for pat in ["campaign", "Shared link", "Shutdown tab", "Defaults", "Log in", "Bulk", "Setup", "resting (Shutdown", "account-workspace"]:
    idx = b.find(pat)
    out.append(f"{pat}: {'FOUND at '+str(idx) if idx>=0 else 'NO'}")
    if idx >= 0:
        out.append("  " + b[max(0,idx-100):idx+200].replace("\n", " "))

# find Tk-like filter
for pat in ["on shutdown list", "filter", "shutdown_list", "loggedIn", "logged-in"]:
    for m in re.finditer(pat, b):
        if m.start() > 500000:  # skip xlsx junk
            out.append(f"\n{pat}@{m.start()}: {b[m.start():m.start()+120]}")
            break

text = "\n".join(out)
open(os.path.join(os.environ.get("TEMP", "."), "app_bundle_search.txt"), "w", encoding="utf-8").write(text)
print(text[:8000])
