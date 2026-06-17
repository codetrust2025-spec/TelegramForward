#!/usr/bin/env python3
"""Diagnose why Posts today is 0 on VPS."""
from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

import paramiko

HOST = "187.127.169.159"
USER = "root"
PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

REMOTE_SCRIPT = r'''
import json, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30))

sys_path = "/opt/telegramforward.old"
import sys
sys.path.insert(0, sys_path)

from core.stats_reset import get_effective_cutoff, stats_window_kind
from core.daily_stats import compute_daily_stats
from core.send_stats import count_since_cutoff, _load_timestamps
from core.ist_time import ist_date_str, ist_day_start_ts, ist_now

root = Path("/opt/telegramforward.old/data/accounts")
cutoff = get_effective_cutoff()
day_start = ist_day_start_ts()
now = time.time()

print("=== IST window ===")
print("ist_date", ist_date_str())
print("window", stats_window_kind())
print("day_start", ist_now(day_start).isoformat())
print("cutoff", datetime.fromtimestamp(cutoff, tz=IST).isoformat())
print("cutoff_age_h", round((now - cutoff) / 3600, 2))

slots = sorted(p.name for p in root.iterdir() if p.is_dir() and p.name.startswith("account"))
daily = compute_daily_stats(slots)
g = daily.get("global") or {}
print("\n=== Fleet daily_stats global ===")
print("forward_posts", g.get("forward_posts"))
print("campaign_posts", g.get("campaign_posts"))
print("forwarded", g.get("forwarded"))

print("\n=== Per account since cutoff ===")
for slot in slots:
    fwd = count_since_cutoff(slot, cutoff, "forward")
    camp = count_since_cutoff(slot, cutoff, "campaign")
    leg = count_since_cutoff(slot, cutoff, None)
    hist_fwd = Path(f"/opt/telegramforward.old/data/accounts/{slot}/send_history_forward.json")
    hist_camp = Path(f"/opt/telegramforward.old/data/accounts/{slot}/send_history_campaign.json")
    hist = Path(f"/opt/telegramforward.old/data/accounts/{slot}/send_history.json")
    ts_all = _load_timestamps(slot, None)
    since = [t for t in ts_all if t >= cutoff]
    last = max(ts_all) if ts_all else None
    last_ist = datetime.fromtimestamp(last, tz=IST).isoformat() if last else "never"
    print(f"{slot}: fwd={fwd} camp={camp} legacy={leg} raw_since_cutoff={len(since)} last_send={last_ist} files={hist_fwd.exists()}/{hist_camp.exists()}/{hist.exists()}")

print("\n=== stats_reset.json ===")
p = Path("/opt/telegramforward.old/data/stats_reset.json")
if p.exists():
    print(json.dumps(json.loads(p.read_text()), indent=2)[:800])
else:
    print("(missing)")

print("\n=== Worker tick sample (account1,4 forward) ===")
import subprocess
for acc in ["account1", "account4", "account3"]:
    r = subprocess.run(
        ["pm2", "logs", acc, "--lines", "8", "--nostream"],
        capture_output=True, text=True, timeout=15
    )
    lines = [l for l in (r.stdout or "").splitlines() if l.strip()][-6:]
    print(f"--- {acc} ---")
    for l in lines:
        print(l[:200])
'''


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    cmd = (
        f"cd {REMOTE} && source venv/bin/activate && python3 << 'PYEOF'\n"
        f"{REMOTE_SCRIPT}\nPYEOF"
    )
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode())
    err = e.read().decode().strip()
    if err:
        print("STDERR:", err, file=sys.stderr)
    c.close()


if __name__ == "__main__":
    main()
