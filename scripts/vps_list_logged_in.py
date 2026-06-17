#!/usr/bin/env python3
import os, socket, paramiko, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

script = r'''
import json, os, glob
from core.config import ACCOUNT_SLOTS
from core.account_info_store import load_account_info

logged = []
for slot in ACCOUNT_SLOTS:
    info = load_account_info(slot)
    if info and info.get("phone"):
        logged.append((slot, info))

print("LOGGED IN COUNT:", len(logged))
for slot, info in logged:
    print(json.dumps({
        "slot": slot,
        "name": info.get("name"),
        "display_name": info.get("display_name"),
        "first_name": info.get("first_name"),
        "phone": info.get("phone"),
    }, ensure_ascii=False))

# search UpdateProfile in py only
import subprocess
r = subprocess.run(
    ["grep", "-rn", "UpdateProfile", "/opt/telegramforward.old/core", "/opt/telegramforward.old/server.py"],
    capture_output=True, text=True
)
print("UpdateProfile hits:", r.stdout or r.stderr or "none")
'''

cmd = f"cd /opt/telegramforward.old && python3 - <<'PY'\n{script}\nPY"
_, stdout, stderr = c.exec_command(cmd, timeout=60)
print(stdout.read().decode(errors="replace"))
err = stderr.read().decode(errors="replace")
if err.strip():
    print("ERR:", err)
c.close()
