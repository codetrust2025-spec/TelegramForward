#!/usr/bin/env python3
import socket, paramiko, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

script = r'''
import json, urllib.request
# login + state
import os
from pathlib import Path
env = {}
for line in Path("/opt/telegramforward.old/.env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k,v = line.split("=",1)
        env[k.strip()] = v.strip().strip('"').strip("'")
pw = env.get("DASHBOARD_PASSWORD","")
req = urllib.request.Request("http://127.0.0.1:8000/api/login", data=json.dumps({"username":"admin","password":pw}).encode(), headers={"Content-Type":"application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=15) as r:
    cookie = r.headers.get("Set-Cookie","")
sess = cookie.split("ta_session=")[1].split(";")[0] if "ta_session=" in cookie else ""
req2 = urllib.request.Request("http://127.0.0.1:8000/api/state", headers={"Cookie": f"ta_session={sess}"})
with urllib.request.urlopen(req2, timeout=15) as r:
    state = json.loads(r.read())
fwd = ["account1","account2","account4","account6","account9"]
modes = state.get("posting_modes") or {}
st = state.get("account_states") or {}
print("FORWARDING ACCOUNTS next_cycle_in / status:")
mins = []
for slot in fwd:
    a = st.get(slot) or {}
    n = a.get("next_cycle_in") or 0
    if n: mins.append((n, slot))
    print(f"  {slot}: status={a.get('status')} running={a.get('running')} fwd_running={a.get('forwarding_running')} next_cycle_in={n}s ({n//60}m {n%60}s)")
if mins:
    m = min(mins)
    print(f"MIN (fleet sleeping timer): {m[0]}s = {m[0]//60}m {m[0]%60}s on {m[1]}")
else:
    print("No next_cycle_in > 0")
'''
_, stdout, stderr = c.exec_command(f"cd /opt/telegramforward.old && ./venv/bin/python - <<'PY'\n{script}\nPY", timeout=60)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err: print("ERR:", err)
c.close()
