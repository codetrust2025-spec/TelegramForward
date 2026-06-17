#!/usr/bin/env python3
"""Fetch send_stats and account logs for shutdown accounts."""
from __future__ import annotations

import os
import sys

import paramiko

PASSWORD = os.environ.get("VPS_PASSWORD", "")
ROOT = "/opt/telegramforward.old"

REMOTE = r'''
import json, os, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/opt/telegramforward.old")
sys_path = str(ROOT)
import sys
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

os.chdir(ROOT)

from core.send_stats import get_last_post_timestamp, count_since_cutoff
from core.group_send_stats import count_group_sends_since_cutoff
from core.stats_reset import get_effective_cutoff
from core.account_shutdown import evaluate_posting_idle, NO_POST_THRESHOLD_SECONDS

slots = ["account1", "account2", "account4", "account8"]
shutdown = json.loads((ROOT / "data/account_shutdown.json").read_text()).get("accounts", {})

# list data files
print("DATA FILES:")
for p in sorted((ROOT / "data").glob("*")):
    if any(s in p.name for s in slots) and p.is_file():
        print(" ", p.name, p.stat().st_size)

print("\nSEND_STATS MODULE:")
import inspect
import core.send_stats as ss
print(inspect.getsourcefile(ss))

for s in slots:
    print("\n===", s, "===")
    rec = shutdown.get(s, {})
    last = get_last_post_timestamp(s)
    cutoff = get_effective_cutoff(s, time.time())
    forwards = count_since_cutoff(s, cutoff)
    gs = count_group_sends_since_cutoff(s, cutoff)
    print("get_last_post_timestamp:", last, datetime.fromtimestamp(last, tz=timezone.utc).isoformat() if last else None)
    print("get_effective_cutoff:", cutoff, datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat() if cutoff else None)
    print("count_since_cutoff:", forwards)
    print("count_group_sends_since_cutoff:", gs)
    print("NO_POST_THRESHOLD:", NO_POST_THRESHOLD_SECONDS)
    print("idle_from_last_post:", time.time()-last if last else None)
    print("window_idle:", time.time()-cutoff if cutoff else None)
    print("shutdown_record:", json.dumps(rec, indent=2))

    # worker state from manager persistence
    for fname in ["worker_persist.json", "running_slots.json", "account_metrics.json"]:
        p = ROOT / "data" / fname
        if p.exists() and s in p.read_text():
            print(fname, "mentions", s)

# send_stats json paths
for s in slots:
    for pat in [f"send_stats/{s}.json", f"send_stats_{s}.json", f"posts/{s}.json"]:
        p = ROOT / "data" / pat
        if p.exists():
            print(s, pat, p.read_text()[:2000])

# account logs tail
log_dir = ROOT / "data" / "logs"
if log_dir.exists():
    for s in slots:
        matches = list(log_dir.glob(f"*{s}*")) + list(log_dir.glob(f"{s}*"))
        for lp in matches[:3]:
            lines = lp.read_text(errors="replace").splitlines()
            hits = [ln for ln in lines if any(k in ln.lower() for k in ["success", "fail", "shutdown", "auto-shutdown", "sent", "skip", "error", "flood"])]
            print("\nLOG", lp.name, "tail hits:")
            for ln in hits[-15:]:
                print(ln[:300])

# postgres send history if exists
try:
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k,v = line.split("=",1); env[k.strip()] = v.strip().strip('"')
    url = env.get("DATABASE_URL") or env.get("POSTGRES_URL")
    if url:
        import psycopg2
        conn = psycopg2.connect(url)
        cur = conn.cursor()
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")
        tables = [r[0] for r in cur.fetchall()]
        print("\nPG TABLES:", tables)
        for t in tables:
            if any(x in t for x in ["send", "post", "message", "forward", "stat"]):
                cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name=%s", (t,))
                cols = [r[0] for r in cur.fetchall()]
                print("TABLE", t, "cols", cols)
        conn.close()
except Exception as e:
    print("PG:", e)

# grep account logs in pm2 for shutdown events
'''


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", "root", PASSWORD, timeout=30)
    _, o, _ = c.exec_command(f"python3 - <<'PY'\n{REMOTE}\nPY", timeout=180)
    print(o.read().decode("utf-8", errors="replace"))
    _, o2, _ = c.exec_command(
        "grep -iE 'account4|account8' /root/.pm2/logs/telegram-backend-out.log 2>/dev/null | "
        "grep -iE 'Auto-shutdown|auto-shutdown|no_post' | tail -20",
        timeout=60,
    )
    print("\n=== account4/8 shutdown log lines ===")
    print(o2.read().decode("utf-8", errors="replace"))
    c.close()


if __name__ == "__main__":
    main()
