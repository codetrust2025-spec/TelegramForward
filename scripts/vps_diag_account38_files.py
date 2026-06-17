#!/usr/bin/env python3
"""Diagnose account3/account8 from VPS data files directly."""
import json
import os
import socket
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

DIAG = '''
import json
from pathlib import Path

BASE = Path("/opt/telegramforward.old/data")
slots = ["account3", "account8"]
out = {}

for s in slots:
    d = {"slot": s}
    for name in ["cycle_metrics_last.json", "groups_health.json", "group_send_history.json"]:
        p = BASE / s / name
        if p.exists():
            raw = json.loads(p.read_text())
            if name == "groups_health.json":
                if isinstance(raw, dict) and "buckets" in raw:
                    b = raw["buckets"]
                else:
                    b = raw if isinstance(raw, dict) else {}
                healthy = len(b.get("healthy") or [])
                blocked = len(b.get("blocked") or [])
                skipped = len(b.get("skipped") or [])
                d["groups_health"] = {"healthy": healthy, "blocked": blocked, "skipped": skipped}
            elif name == "group_send_history.json":
                entries = raw if isinstance(raw, list) else raw.get("entries", [])
                d["send_history_count"] = len(entries)
                d["last_send"] = entries[-1] if entries else None
            else:
                d["cycle_metrics"] = raw
        else:
            d[name.replace(".json","")] = None

    msg = BASE / s / "message.txt"
    d["has_message"] = msg.exists()
    if msg.exists():
        d["message_len"] = len(msg.read_text(encoding="utf-8", errors="replace"))

    gi = BASE / "group_intelligence.json"
    if gi.exists():
        gi_data = json.loads(gi.read_text())
        acct_intel = gi_data.get("accounts", {}).get(s, {})
        d["intel"] = {
            "health_score": acct_intel.get("health_score"),
            "execution_policy": acct_intel.get("execution_policy"),
            "flood_streak": acct_intel.get("flood_streak"),
        }

    cfg_path = BASE / "accounts_config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        d["config"] = cfg.get(s, {})

    shutdown = BASE / "account_shutdown.json"
    if shutdown.exists():
        sd = json.loads(shutdown.read_text())
        d["on_shutdown_list"] = s in (sd.get("accounts") or sd.get("slots") or [])

    out[s] = d

print(json.dumps(out, indent=2))

# tail account logs if present
for s in slots:
    log_dir = BASE / s / "logs"
    if log_dir.exists():
        files = sorted(log_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if files:
            lines = files[0].read_text(encoding="utf-8", errors="replace").strip().split("\\n")[-8:]
            print(f"\\n=== {s} recent log lines ===")
            for ln in lines:
                print(ln[:200])
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/diag_acct2.py", "w") as f:
    f.write(DIAG)
sftp.close()
_, stdout, stderr = c.exec_command(f"/opt/telegramforward.old/venv/bin/python /tmp/diag_acct2.py", timeout=60)
print(stdout.read().decode("utf-8", errors="replace"))
err = stderr.read().decode("utf-8", errors="replace")
if err.strip():
    print("ERR:", err)

# grep feature_runtime fix is present
_, stdout, _ = c.exec_command(
    f"grep -c '_SHARED_ALIASES' {REMOTE}/workers/feature_runtime.py; "
    f"grep -c 'campaign_runtime(self.state)' {REMOTE}/workers/account_worker.py",
    timeout=15,
)
print("\n=== FIX MARKERS ON VPS ===")
print(stdout.read().decode())

c.close()
