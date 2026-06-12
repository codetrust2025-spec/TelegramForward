#!/usr/bin/env python3
import socket, paramiko, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

script = r'''
import json, http.cookiejar, urllib.request
from pathlib import Path
pw = ""
for line in Path("/opt/telegramforward.old/.env").read_text().splitlines():
    if line.startswith("DASHBOARD_PASSWORD="):
        pw = line.split("=",1)[1].strip().strip('"').strip("'")
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
login = urllib.request.Request(
    "http://127.0.0.1:8000/api/login",
    data=json.dumps({"username":"admin","password":pw}).encode(),
    headers={"Content-Type":"application/json"},
    method="POST",
)
with opener.open(login, timeout=15) as r:
    r.read()
req = urllib.request.Request("http://127.0.0.1:8000/api/state")
with opener.open(req, timeout=15) as r:
    state = json.loads(r.read())
fwd = ["account1","account2","account4","account6","account9"]
st = state.get("account_states") or {}
status = state.get("account_status") or {}
print("LIVE forwarding rest:")
mins = []
for slot in fwd:
    a = st.get(slot) or {}
    lc = (status.get(slot) or {}).get("lifecycle")
    n = int(a.get("next_cycle_in") or 0)
    print(f"  {slot}: lifecycle={lc} next_cycle_in={n}s ({n//60}m {n%60:02d}s)")
    if n > 0: mins.append((n, slot))
if mins:
    m = min(mins)
    print(f"=> Fleet sleeping timer: {m[0]//60}m {m[0]%60:02d}s (shortest on {m[1]})")
else:
    print("=> No active rest countdown")
'''
_, stdout, stderr = c.exec_command(f"cd /opt/telegramforward.old && ./venv/bin/python - <<'PY'\n{script}\nPY", timeout=60)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip(): print("ERR:", err[-2000:])
c.close()
