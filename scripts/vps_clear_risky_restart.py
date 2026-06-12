#!/usr/bin/env python3
"""Clear risky cooldowns for account3/8 and restart campaign workers."""
import os
import socket
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

SCRIPT = '''
import json, time, urllib.request, sys
from pathlib import Path
sys.path.insert(0, "/opt/telegramforward.old")
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE

def clear_risky(slot):
    gi_path = Path(f"/opt/telegramforward.old/data/accounts/{slot}/group_intelligence.json")
    gi = json.loads(gi_path.read_text())
    groups = gi.get("groups", {})
    cleared = 0
    for g, info in groups.items():
        if isinstance(info, dict) and info.get("risky_until"):
            info["risky_until"] = 0
            cleared += 1
    gi_path.write_text(json.dumps(gi, indent=2))
    gh_path = Path(f"/opt/telegramforward.old/data/accounts/{slot}/groups_health.json")
    if gh_path.exists():
        gh = json.loads(gh_path.read_text())
        detail = gh.get("detail") or {}
        for g, d in detail.items():
            if isinstance(d, dict) and d.get("bucket") == "risky":
                d["risky_until"] = 0
        gh_path.write_text(json.dumps(gh, indent=2))
    print(f"{slot}: cleared risky_until on {cleared} groups")

for slot in ["account3", "account8"]:
    clear_risky(slot)

user, pw = get_credentials()
token = create_session_token(user, role="admin")

def post(path):
    req = urllib.request.Request("http://127.0.0.1:8000" + path, method="POST", data=b"")
    req.add_header("Cookie", f"{SESSION_COOKIE}={token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()

Path("/opt/telegramforward.old/data/account_shutdown.json").write_text('{"accounts": {}}')

for slot in ["account3", "account8"]:
    try:
        post(f"/account/{slot}/stop?feature=campaign")
    except Exception:
        pass
    time.sleep(1)
    print(slot, post(f"/account/{slot}/start?feature=campaign"))

print("sleep 220s")
time.sleep(220)
for slot in ["account3", "account8", "account5"]:
    cm = json.loads(Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json").read_text())
    age = int(time.time() - float(cm.get("ended_at") or 0))
    print(f"{slot}: success={cm.get('success')} skipped={cm.get('skipped')} failed={cm.get('failed')} cycle={cm.get('cycle_number')} age={age}s")
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/clear_risky.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, _ = c.exec_command(f"{REMOTE}/venv/bin/python /tmp/clear_risky.py 2>&1", timeout=260)
print(stdout.read().decode())
c.close()
