#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
REMOTE = r'''
import json
from pathlib import Path
ROOT = Path("/opt/telegramforward.old")

from core.groups_store import load_master_groups, groups_readonly_snapshot_for_slot

master = load_master_groups()
print(f"MASTER GROUPS: {len(master)}")
if master:
    print(f"  sample: {master[:3]}")

for slot in ["account3", "account5", "account7", "account10", "account1"]:
    snap = groups_readonly_snapshot_for_slot(slot)
    print(f"{slot} snapshot: {len(snap)} groups")
    if snap:
        print(f"  sample: {snap[:2]}")

# find master groups file path
import core.groups_store as gs
import inspect
src = inspect.getsourcefile(gs)
print(f"\ngroups_store at: {src}")
# read DATA_DIR
from core.config import DATA_DIR, STATE_DIR
print(f"DATA_DIR={DATA_DIR} STATE_DIR={STATE_DIR}")

for pattern in ["groups.txt", "groups.json", "master_groups*"]:
    import glob
    for p in glob.glob(str(Path(DATA_DIR) / "**" / pattern), recursive=True):
        print(f"  found: {p}")

# Check account dead groups
from core.groups_store import load_account_dead
for slot in ["account3", "account5", "account7"]:
    inv, blk = load_account_dead(slot)
    print(f"{slot} invalid={len(inv)} blocked={len(blk)}")

# Trigger refresh joined for account7 and see result
import urllib.request, http.cookiejar
pw = next(l.split("=",1)[1].strip().strip('"') for l in (ROOT/".env").read_text().splitlines() if l.startswith("DASHBOARD_PASSWORD="))
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.open(urllib.request.Request("http://127.0.0.1:8000/auth/login", json.dumps({"username":"admin","password":pw}).encode(),
    headers={"Content-Type":"application/json"}, method="POST"))
req = urllib.request.Request("http://127.0.0.1:8000/account/refresh-joined",
    json.dumps({"slot": "account7"}).encode(), headers={"Content-Type":"application/json"}, method="POST")
with op.open(req, timeout=120) as r:
    res = json.loads(r.read().decode())
    print(f"\nrefresh-joined account7: {json.dumps(res, ensure_ascii=False)[:500]}")

snap2 = groups_readonly_snapshot_for_slot("account7")
print(f"account7 snapshot AFTER refresh: {len(snap2)}")
'''
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, stderr = c.exec_command(
    f"cd /opt/telegramforward.old && set -a && . ./.env && set +a && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE}\nPY",
    timeout=150,
)
print(stdout.read().decode("utf-8", errors="replace"))
print(stderr.read().decode("utf-8", errors="replace")[-3000:])
c.close()
