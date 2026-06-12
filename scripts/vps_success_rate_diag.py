#!/usr/bin/env python3
"""Diagnose success rate / tick metrics on VPS."""
import json
import os
import socket
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")

SCRIPT = r'''
import json, time, urllib.request, sys
from pathlib import Path
sys.path.insert(0, "/opt/telegramforward.old")
from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE

user, pw = get_credentials()
token = create_session_token(user, role="admin")
req = urllib.request.Request("http://127.0.0.1:8000/state")
req.add_header("Cookie", f"{SESSION_COOKIE}={token}")
state = json.loads(urllib.request.urlopen(req, timeout=20).read())

# Fleet-level tick stats if present
for k in ["total", "success", "failed", "skipped", "notification", "running"]:
    if k in state:
        print(f"fleet.{k} = {state.get(k)}")

ac = state.get("account_states") or {}
forwarding = []
campaign = []
for slot, a in sorted(ac.items()):
    if not a.get("running"):
        continue
    row = {
        "slot": slot,
        "campaign": a.get("campaign_running"),
        "forwarding": a.get("forwarding_running"),
        "success": a.get("success"),
        "failed": a.get("failed"),
        "skipped": a.get("skipped_already_posted"),
        "cycle": a.get("cycle"),
        "status": a.get("status"),
        "next_cycle_in": a.get("next_cycle_in"),
        "health": a.get("health_score"),
        "current_group": a.get("current_group"),
    }
    if a.get("forwarding_running"):
        forwarding.append(row)
    elif a.get("campaign_running"):
        campaign.append(row)

print("\n=== FORWARDING ACCOUNTS ===")
for r in forwarding:
    print(r)

print("\n=== CAMPAIGN ACCOUNTS ===")
for r in campaign:
    print(r)

# Recent failed from metrics/alerts
alerts = state.get("alerts") or state.get("fleet_alerts") or []
if alerts:
    print("\n=== ALERTS (last 8) ===")
    for a in alerts[-8:]:
        print(a if isinstance(a, str) else json.dumps(a)[:200])

# Per-account cycle metrics + failed lists
print("\n=== LAST CYCLE METRICS ===")
for slot in sorted(ac.keys()):
    p = Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json")
    if not p.exists():
        continue
    cm = json.loads(p.read_text())
    age = int(time.time() - float(cm.get("ended_at") or 0))
    if age > 3600:
        continue
    sr = cm.get("success_rate")
    print(f"{slot}: success={cm.get('success')} failed={cm.get('failed')} skipped={cm.get('skipped')} "
          f"rate={sr}% age={age}s groups={cm.get('groups_processed')}")

# Forwarding tick failures - check failed_list in state
print("\n=== FORWARDING FAILED LISTS (this session) ===")
for slot in ["account1", "account2", "account4", "account6", "account9"]:
    a = ac.get(slot, {})
    fl = a.get("failed_list") or []
    if fl:
        print(f"{slot}: {len(fl)} failed entries, last 3: {fl[-3:]}")

# Fleet sleep / timing
try:
    from core.account_timing import fleet_timing_snapshot
    snap = fleet_timing_snapshot()
    print("\n=== FLEET TIMING ===")
    print(json.dumps(snap, indent=2, default=str)[:1500])
except Exception as e:
    print("fleet timing err:", e)

# Daily stats
try:
    from core.daily_stats import compute_daily_stats
    from core.config import ACCOUNTS
    ds = compute_daily_stats(list(ACCOUNTS))
    print("\n=== DAILY STATS (summary) ===")
    print(f"forward_posts_24h={ds.get('forward_posts_24h')} campaign_posts_24h={ds.get('campaign_posts_24h')}")
except Exception as e:
    print("daily stats err:", e)
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/success_rate_diag.py", "w") as f:
    f.write(SCRIPT)
sftp.close()
_, stdout, stderr = c.exec_command(
    "/opt/telegramforward.old/venv/bin/python /tmp/success_rate_diag.py 2>&1",
    timeout=90,
)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip():
    print("ERR:", err[:1000])
c.close()
