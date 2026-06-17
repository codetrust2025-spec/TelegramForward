#!/usr/bin/env python3
"""Diagnose account3/account8 campaign posting on VPS."""
import json
import os
import socket
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
BASE = "/opt/telegramforward.old/data"

DIAG = r'''
import json, urllib.request, base64
from pathlib import Path

BASE = Path("/opt/telegramforward.old/data")
slots = ["account3", "account8"]

# Live state
req = urllib.request.Request("http://127.0.0.1:8000/state")
cred = base64.b64encode(b"admin:734720077743").decode()
req.add_header("Authorization", "Basic " + cred)
state = json.loads(urllib.request.urlopen(req, timeout=15).read())

out = {}
for s in slots:
    d = {"slot": s}
    ac = state.get("accounts", {}).get(s, {})
    d["live"] = {
        k: ac.get(k)
        for k in [
            "running", "campaign_running", "forwarding_running", "status",
            "success", "failed", "skipped", "health_score", "execution_policy",
            "shutdown_reason", "cycle", "current_group", "next_cycle_in",
            "campaign_posts_24h", "heavy_rate_limit",
        ]
    }
    for name in ["cycle_metrics_last.json", "groups_health.json", "group_send_history.json"]:
        p = BASE / s / name
        if p.exists():
            raw = json.loads(p.read_text())
            if name == "groups_health.json":
                buckets = raw.get("buckets", raw) if isinstance(raw, dict) else {}
                healthy = sum(1 for g in (buckets.get("healthy") or []) if g)
                blocked = sum(1 for g in (buckets.get("blocked") or []) if g)
                skipped = sum(1 for g in (buckets.get("skipped") or []) if g)
                d[name] = {"healthy": healthy, "blocked": blocked, "skipped": skipped, "total": healthy + blocked + skipped}
            elif name == "group_send_history.json":
                d[name] = {"count": len(raw) if isinstance(raw, list) else len(raw.get("entries", []))}
            else:
                d[name] = raw
        else:
            d[name] = None
    msg = BASE / s / "message.txt"
    d["has_message"] = msg.exists()
    if msg.exists():
        d["message_preview"] = msg.read_text(encoding="utf-8", errors="replace")[:80]
    gi = BASE / "group_intelligence.json"
    if gi.exists():
        gi_data = json.loads(gi.read_text())
        d["intel_health"] = gi_data.get("accounts", {}).get(s, {}).get("health_score")
    cfg_path = BASE / "accounts_config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        d["config"] = {k: cfg.get(s, {}).get(k) for k in ["output_mode", "campaign_enabled", "forwarding_enabled"]}
    out[s] = d

print(json.dumps(out, indent=2))
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

# Write and run diag on server
sftp = c.open_sftp()
with sftp.open("/tmp/diag_acct.py", "w") as f:
    f.write(DIAG)
sftp.close()

_, stdout, stderr = c.exec_command(
    f"/opt/telegramforward.old/venv/bin/python /tmp/diag_acct.py 2>&1",
    timeout=60,
)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err:
    print("STDERR:", err)

# Recent worker logs for these accounts
_, stdout, _ = c.exec_command(
    "grep -E 'account3|account8' /root/.pm2/logs/telegram-backend-out.log 2>/dev/null | tail -30",
    timeout=30,
)
print("\n=== PM2 OUT (last 30 matching) ===")
print(stdout.read().decode("utf-8", errors="replace")[:5000])

c.close()
