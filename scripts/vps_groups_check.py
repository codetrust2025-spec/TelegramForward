#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
REMOTE = r'''
import json, os
from pathlib import Path
ROOT = Path("/opt/telegramforward.old")

print("=== GLOBAL GROUPS ===")
for p in [ROOT/"data/groups.txt", ROOT/"data/groups.json", ROOT/"data/total_groups.txt"]:
    if p.exists():
        print(f"{p.name}: {p.stat().st_size} bytes, lines={sum(1 for _ in open(p,encoding='utf-8',errors='ignore'))}")

print("\n=== PER-ACCOUNT DATA DIRS ===")
for slot in [f"account{i}" for i in range(1,11)]:
    d = ROOT / "data" / "accounts" / slot
    if not d.exists():
        continue
    files = list(d.iterdir())
    names = [f.name for f in files]
    print(f"{slot}: {names}")

print("\n=== STATE total / my_groups from API ===")
import urllib.request, http.cookiejar, json as j
pw = next(l.split("=",1)[1].strip().strip('"') for l in (ROOT/".env").read_text().splitlines() if l.startswith("DASHBOARD_PASSWORD="))
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def api(path):
    req = urllib.request.Request(f"http://127.0.0.1:8000{path}")
    with op.open(req, timeout=30) as r:
        return j.loads(r.read().decode())
op.open(urllib.request.Request("http://127.0.0.1:8000/auth/login", j.dumps({"username":"admin","password":pw}).encode(),
    headers={"Content-Type":"application/json"}, method="POST"))
st = api("/state")
print(f"state.total={st.get('total')}")
for slot in [f"account{i}" for i in range(1,11)]:
    a = st.get("account_states",{}).get(slot,{})
    if a:
        print(f"  {slot}: my_groups={len(a.get('my_groups') or [])} running={a.get('running')} camp={a.get('campaign_running')} fwd={a.get('forwarding_running')} status={a.get('status')} notif={str(a.get('notification') or '')[:80]}")

print("\n=== PM2 OUT LOG errors ===")
import subprocess
r = subprocess.run(["pm2", "logs", "telegram-backend", "--lines", "500", "--nostream"],
    capture_output=True, text=True, timeout=60)
for line in (r.stdout + r.stderr).splitlines():
    if "out.log" not in line and "error.log" in line:
        continue
    ll = line.lower()
    if any(k in ll for k in ["error", "exception", "traceback", "no groups", "my_groups", "groups.txt", "send_fail", "appledeveloper", "recovering", "retry"]):
        if "|telegram |" in line:
            line = line.split("|telegram |", 1)[-1].strip()
        if line.startswith("[") or "ERROR" in line or "Error" in line or "SEND" in line or "groups" in ll:
            print(line[:250])
'''
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, _ = c.exec_command(f"cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE}\nPY", timeout=90)
print(stdout.read().decode("utf-8", errors="replace"))
c.close()
