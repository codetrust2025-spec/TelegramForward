#!/usr/bin/env python3
"""Analyze why account3/8 skip all groups; apply targeted unblock."""
import json
import os
import socket
import sys
import time

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
BASE = f"{REMOTE}/data/accounts"

FIX = '''
import json
import hashlib
from pathlib import Path

BASE = Path("/opt/telegramforward.old/data/accounts")
msg_hash = hashlib.sha256(Path("/opt/telegramforward.old/data/fleet_defaults.json").read_text().encode()).hexdigest()[:12]

for slot in ["account3", "account8"]:
    acct = BASE / slot
    gi_path = acct / "group_intelligence.json"
    gi = json.loads(gi_path.read_text())
    groups = gi.get("groups", {})
    
    # Count skip drivers in assigned rotation
    blocked_path = acct / "blocked_groups.json"
    blocked = set()
    if blocked_path.exists():
        raw = json.loads(blocked_path.read_text())
        if isinstance(raw, list):
            blocked = set(raw)
        elif isinstance(raw, dict):
            blocked = set(raw.keys())
    
    stats = {"blocked_list": len(blocked), "intel_blocked": 0, "intel_skipped": 0, 
             "intel_sent": 0, "recent_touch": 0, "join_limited": 0}
    for g, info in groups.items():
        if not isinstance(info, dict):
            continue
        r = info.get("last_result") or info.get("status")
        if r == "blocked":
            stats["intel_blocked"] += 1
        elif r == "skipped":
            stats["intel_skipped"] += 1
        elif r in ("sent", "joined_sent"):
            stats["intel_sent"] += 1
        elif r == "join_limited":
            stats["join_limited"] += 1
        ts = info.get("last_touch_ts") or info.get("last_attempt_ts") or 0
        if ts and time.time() - float(ts) < 3600:
            stats["recent_touch"] += 1
    
    print(f"\\n{slot} intel stats:", stats)
    print(f"  blocked sample:", list(blocked)[:5])

import time
'''

# Simpler: get recent account logs from state file or grep worker internal logs
DIAG = '''
import json, re
from pathlib import Path

for slot in ["account3", "account8"]:
    # Read last lines from PM2 error log mentioning slot and skip
    log = Path("/root/.pm2/logs/telegram-backend-out.log")
    if not log.exists():
        continue
    text = log.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in text.split("\\n") if slot in ln and any(x in ln.lower() for x in ["skip", "posted", "latest", "cannot", "cooldown", "cycle"])]
    print(f"\\n=== {slot} log hints (last 15) ===")
    for ln in lines[-15:]:
        print(ln[:250])
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

# Get account worker in-memory logs via API if exists
_, stdout, _ = c.exec_command(
    f"grep -E 'account3|account8' /root/.pm2/logs/telegram-backend-error.log 2>/dev/null | tail -20; "
    f"grep -E 'Skipped|already|latest|Cannot post|↷' /root/.pm2/logs/telegram-backend-out.log 2>/dev/null | grep -E 'account3|account8' | tail -15",
    timeout=30,
)
print("=== WORKER LOGS ===")
print(stdout.read().decode("utf-8", errors="replace")[:4000])

# Read groups_health full for account3
_, stdout, _ = c.exec_command(
    f"python3 -c \"import json; d=json.load(open('{BASE}/account3/groups_health.json')); print(json.dumps(d, indent=2)[:3000])\"",
    timeout=20,
)
print("\n=== account3 groups_health ===")
print(stdout.read().decode())

c.close()
