#!/usr/bin/env python3
import socket, paramiko, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
REMOTE = r'''
import json
from pathlib import Path
ROOT = Path("/opt/telegramforward.old")

for slot in ["account3", "account5", "account7", "account10", "account1"]:
    d = ROOT / "data" / "accounts" / slot
    print(f"\n=== {slot} ===")
    for fname in ["join_state.json", "group_intelligence.json", "groups_health.json", "blocked_groups.json"]:
        p = d / fname
        if not p.exists():
            print(f"  {fname}: MISSING")
            continue
        raw = json.loads(p.read_text(encoding="utf-8"))
        if fname == "join_state.json":
            keys = list(raw.keys())[:5] if isinstance(raw, dict) else type(raw)
            joined = raw.get("joined") or raw.get("groups") or raw.get("targets") or []
            if isinstance(joined, dict):
                joined = list(joined.keys())
            print(f"  join_state keys={list(raw.keys())[:8]} joined_count={len(joined) if isinstance(joined, list) else 'n/a'}")
            if isinstance(raw, dict) and "joined_count" in raw:
                print(f"    joined_count field={raw.get('joined_count')}")
        elif fname == "groups_health.json":
            g = raw.get("groups") or []
            print(f"  groups_health: {len(g)} groups")
        elif fname == "blocked_groups.json":
            b = raw if isinstance(raw, list) else raw.get("groups") or raw.get("blocked") or []
            print(f"  blocked: {len(b) if isinstance(b, (list,dict)) else raw}")
        elif fname == "group_intelligence.json":
            if isinstance(raw, dict):
                print(f"  group_intelligence keys={len(raw)}")

# Where does total=269 come from
print("\n=== TOTAL 269 SOURCE ===")
import urllib.request, http.cookiejar
pw = next(l.split("=",1)[1].strip().strip('"') for l in (ROOT/".env").read_text().splitlines() if l.startswith("DASHBOARD_PASSWORD="))
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.open(urllib.request.Request("http://127.0.0.1:8000/auth/login", json.dumps({"username":"admin","password":pw}).encode(),
    headers={"Content-Type":"application/json"}, method="POST"))
req = urllib.request.Request("http://127.0.0.1:8000/groups/list")
try:
    with op.open(req, timeout=30) as r:
        data = json.loads(r.read().decode())
        print(f"groups/list keys: {list(data.keys())[:10]}")
        if "groups" in data:
            print(f"  groups count={len(data['groups'])}")
        if "active_count" in data:
            print(f"  active_count={data.get('active_count')} total={data.get('total')}")
except Exception as e:
    print(f"groups/list error: {e}")

# grep worker for my_groups population
import subprocess
r = subprocess.run(["grep", "-rn", "my_groups", "/opt/telegramforward.old/workers/account_worker.py"], capture_output=True, text=True)
print("\nmy_groups in worker (first 10 lines):")
for line in r.stdout.splitlines()[:10]:
    print(line[:120])

# Get actual worker error from logs - search out log
r2 = subprocess.run(["tail", "-n", "150", "/root/.pm2/logs/telegram-backend-out.log"], capture_output=True, text=True)
for line in r2.stdout.splitlines():
    ll = line.lower()
    if any(k in ll for k in ["account3", "account5", "account7", "account8", "account10", "error", "send_fail", "no group", "joined", "membership", "appledeveloper"]):
        print("LOG:", line[:220])
'''
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, stderr = c.exec_command(f"cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE}\nPY", timeout=90)
print(stdout.read().decode("utf-8", errors="replace"))
print(stderr.read().decode("utf-8", errors="replace")[-2000:])
c.close()
