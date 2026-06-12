#!/usr/bin/env python3
"""Search VPS filesystem and PM2 logs for worker skip/send events."""
from __future__ import annotations

import os
import sys

import paramiko

PASSWORD = os.environ.get("VPS_PASSWORD", "")
ROOT = "/opt/telegramforward.old"
SLOTS = ["account1", "account2", "account4", "account8"]

REMOTE = r'''
import json, os, re, gzip
from pathlib import Path
from collections import Counter

ROOT = Path("/opt/telegramforward.old")
DATA = ROOT / "data"
SLOTS = ["account1", "account2", "account4", "account8"]

print("=== send_stats.py (full) ===")
print((ROOT/"core/send_stats.py").read_text())

print("\n=== group_send_stats.py ===")
p = ROOT/"core/group_send_stats.py"
print(p.read_text() if p.exists() else "missing")

print("\n=== DATA tree (state/logs/metrics) ===")
for sub in ["state", "logs", "metrics", "cycle", "daily"]:
    d = DATA / sub
    if d.exists():
        for f in sorted(d.rglob("*"))[:60]:
            if f.is_file():
                print(f"  {f.relative_to(ROOT)} ({f.stat().st_size}b)")

for slot in SLOTS:
    print(f"\n=== FILES for {slot} ===")
    for f in sorted(DATA.rglob(f"*{slot}*"))[:40]:
        if f.is_file() and f.stat().st_size < 500000:
            print(f"  {f.relative_to(ROOT)} ({f.stat().st_size}b)")

# read send_history if any path
for slot in SLOTS:
    for rel in [
        f"data/state/{slot}/send_history.json",
        f"data/{slot}/send_history.json",
        f"state/{slot}/send_history.json",
    ]:
        p = ROOT / rel
        if p.exists():
            print(f"\n{rel}:", p.read_text()[:3000])

# cycle_metrics / daily stats
for slot in SLOTS:
    for pat in [f"cycle_metrics_{slot}.json", f"daily_stats_{slot}.json", f"metrics_{slot}.json"]:
        p = DATA / pat
        if p.exists():
            print(f"\n{pat}:", p.read_text()[:2000])

# .running_workers
rw = DATA / ".running_workers.json"
print("\n.running_workers.json:", rw.read_text() if rw.exists() else "missing")

# stats_reset
sr = DATA / "stats_reset.json"
print("\nstats_reset.json:", sr.read_text() if sr.exists() else "missing")

# Search PM2 logs deeply
pm2_out = Path("/root/.pm2/logs/telegram-backend-out.log")
pm2_err = Path("/root/.pm2/logs/telegram-backend-error.log")

def grep_file(path, slot, patterns, limit=50):
    if not path.exists():
        return
    text = path.read_text(errors="replace")
    lines = []
    for ln in text.splitlines():
        if slot not in ln:
            continue
        ll = ln.lower()
        if any(p in ll for p in patterns):
            lines.append(ln)
    print(f"\n=== {path.name} {slot} ({len(lines)} hits) ===")
    for ln in lines[-limit:]:
        print(ln[:400])

patterns = [
    "skip", "sent", "fail", "flood", "error", "blocked", "still_latest",
    "already_last", "message_recent", "worker start", "worker stop", "cycle_start",
    "no groups", "shutdown", "cooldown", "cant_write", "rate", "sleeping",
    "auto-shutdown", "pre_join", "join_limited", "risky", "recently_processed",
]

for slot in SLOTS:
    grep_file(pm2_out, slot, patterns, 60)
    grep_file(pm2_err, slot, patterns, 30)

# Also search structured log in data/logs
logs_dir = DATA / "logs"
if logs_dir.exists():
    for slot in SLOTS:
        for lf in logs_dir.glob(f"*{slot}*"):
            print(f"\n=== LOG FILE {lf.name} tail ===")
            lines = lf.read_text(errors="replace").splitlines()
            hits = [ln for ln in lines if any(p in ln.lower() for p in patterns)]
            print(f"hits: {len(hits)}")
            for ln in hits[-40:]:
                print(ln[:400])

# Search all json under data for send timestamps
print("\n=== JSON files containing send_history or timestamps ===")
for f in DATA.rglob("*.json"):
    try:
        if f.stat().st_size > 200000:
            continue
        t = f.read_text(errors="replace")
        if "timestamps" in t or "send_history" in t or "last_success" in t:
            if any(s in str(f) for s in SLOTS) or "send" in f.name.lower():
                print(f.relative_to(ROOT), f.stat().st_size)
    except Exception:
        pass

# get_last_post source - maybe postgres in send_stats
import sys
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    import inspect
    from core import send_stats as ss
    if hasattr(ss, "get_last_post_timestamp"):
        print("\nget_last_post_timestamp source:")
        print(inspect.getsource(ss.get_last_post_timestamp))
except Exception as e:
    print("inspect err", e)

print("\nDONE")
'''


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", "root", PASSWORD, timeout=30)
    _, o, e = c.exec_command(f"cd {ROOT} && ./venv/bin/python3 - <<'PY'\n{REMOTE}\nPY", timeout=300)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    c.close()
    path = os.path.join(os.environ.get("TEMP", "."), "vps_worker_logs_search.txt")
    open(path, "w", encoding="utf-8").write(out + "\n" + err)
    print(out[:80000])
    if len(out) > 80000:
        print(f"\n... truncated, full output in {path}")
    if err.strip():
        print("ERR:", err[:2000])

if __name__ == "__main__":
    main()
