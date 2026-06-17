#!/usr/bin/env python3
"""Deep dive: why accounts could not post before shutdown."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
ROOT = "/opt/telegramforward.old"
SLOTS = ["account1", "account2", "account4", "account8"]

REMOTE = r'''
import json, os, re, glob, time
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

ROOT = Path("/opt/telegramforward.old")
DATA = ROOT / "data"
SLOTS = ["account1", "account2", "account4", "account8"]

shutdown = json.loads((DATA / "account_shutdown.json").read_text()).get("accounts", {})

def iso(ts):
    if not ts: return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def read_json(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None

print("=" * 60)
print("STATS RESET")
print("=" * 60)
print((DATA / "stats_reset.json").read_text() if (DATA / "stats_reset.json").exists() else "missing")

print("\n" + "=" * 60)
print("RUNNING SLOTS / WORKER PERSISTENCE")
print("=" * 60)
for fn in ["running_slots.json", "worker_persist.json", "persisted_workers.json"]:
    p = DATA / fn
    if p.exists():
        print(fn, p.read_text()[:2000])

print("\n" + "=" * 60)
print("BLOCK STORE / GROUP BLOCKS")
print("=" * 60)
for fn in ["block_store.json", "blocks.json"]:
    p = DATA / fn
    if p.exists():
        t = p.read_text()
        for s in SLOTS:
            if s in t:
                print(f"--- mentions {s} in {fn} ---")
        print(fn[:3000])

for slot in SLOTS:
    print("\n" + "#" * 70)
    print(f"# SLOT: {slot}")
    rec = shutdown.get(slot, {})
    shut = float(rec.get("shutdown_at") or 0)
    last = rec.get("last_send_at")
    print(f"shutdown_at: {iso(rec.get('shutdown_at'))} reason={rec.get('reason')} was_running={rec.get('was_running')}")
    print(f"last_send_at: {iso(last)}")

    # send history
    sh_paths = [
        DATA / "state" / slot / "send_history.json",
        DATA / slot / "send_history.json",
    ]
    for sp in sh_paths:
        if sp.exists():
            d = read_json(sp)
            ts = d.get("timestamps", d) if isinstance(d, dict) else d
            if isinstance(ts, list):
                ts = sorted(float(t) for t in ts)
                recent = [t for t in ts if shut and t >= shut - 7*86400]
                print(f"send_history {sp}: total={len(ts)} in_7d_before_shutdown={len(recent)}")
                if ts:
                    print(f"  last_5_sends: {[iso(t) for t in ts[-5:]]}")
                    if last:
                        print(f"  gap_last_send_to_shutdown_h: {(shut-float(last))/3600:.2f}")

    # worker snapshot files
    for pat in [f"worker_state_{slot}.json", f"worker_persist_{slot}.json", f"account_metrics_{slot}.json"]:
        p = DATA / pat
        if p.exists():
            print(pat, p.read_text()[:1500])

    # structured logs in data
    log_hits = []
    for lp in sorted(DATA.rglob("*")):
        if not lp.is_file():
            continue
        if slot not in lp.name and slot not in str(lp):
            continue
        if lp.suffix not in (".json", ".jsonl", ".log", ".txt"):
            continue
        try:
            text = lp.read_text(errors="replace")
        except Exception:
            continue
        if len(text) > 500000:
            text = text[-500000:]
        for ln in text.splitlines():
            ll = ln.lower()
            if any(k in ll for k in ["fail", "error", "flood", "skip", "block", "shutdown", "stop", "rate", "ban", "forbidden", "not latest", "still_latest", "cooldown", "sent", "success", "worker start", "worker stop", "disconnect", "session"]):
                if shut:
                    # keep lines near shutdown window - rough filter by account id in line
                    log_hits.append(ln[:400])
        if lp.stat().st_size < 80000 and ("log" in lp.name or slot in lp.name):
            print(f"\n--- small file {lp.relative_to(ROOT)} ({lp.stat().st_size}b) ---")
            print(text[:4000])

    # pm2 log grep for slot
    pm2 = Path("/root/.pm2/logs/telegram-backend-out.log")
    if pm2.exists():
        lines = pm2.read_text(errors="replace").splitlines()
        slot_lines = [ln for ln in lines if slot in ln and any(k in ln.lower() for k in [
            "fail", "error", "flood", "skip", "block", "shutdown", "auto-shutdown", "sent", "success",
            "still_latest", "cooldown", "rate", "worker", "stop", "start", "disconnect", "waiting",
            "no groups", "empty", "health", "sleep", "resting"
        ])]
        print(f"\npm2 log lines mentioning {slot} (filtered): {len(slot_lines)}")
        for ln in slot_lines[-40:]:
            print(ln[:350])

    # account log json in data/logs
    for lp in sorted((DATA / "logs").glob("*")) if (DATA / "logs").exists() else []:
        if slot in lp.name:
            print(f"\n--- account log file {lp.name} tail ---")
            lines = lp.read_text(errors="replace").splitlines()
            for ln in lines[-30:]:
                print(ln[:350])

# global pm2 auto-shutdown and errors
print("\n" + "=" * 60)
print("ALL AUTO-SHUTDOWN LINES IN PM2")
print("=" * 60)
pm2 = Path("/root/.pm2/logs/telegram-backend-out.log")
if pm2.exists():
    for ln in pm2.read_text(errors="replace").splitlines():
        if "auto-shutdown" in ln.lower() or "Auto-shutdown" in ln:
            print(ln)

print("\n" + "=" * 60)
print("RELOAD / SYSTEM LOG")
print("=" * 60)
rl = DATA / "reload.log"
if rl.exists():
    print(rl.read_text()[-8000:])

# try import send_stats on server
print("\n" + "=" * 60)
print("SERVER send_stats get_last_post")
print("=" * 60)
import sys
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
try:
    from core.send_stats import get_last_post_timestamp, count_since_cutoff, _load_timestamps
    from core.stats_reset import get_effective_cutoff
    from core.group_send_stats import count_group_sends_since_cutoff
    now = time.time()
    for slot in SLOTS:
        lp = get_last_post_timestamp(slot)
        cutoff = get_effective_cutoff(slot, now)
        raw = _load_timestamps(slot)
        print(slot, "last_post", iso(lp), "cutoff", iso(cutoff), "raw_timestamps", len(raw),
              "since_cutoff", count_since_cutoff(slot, cutoff), "group_sends", count_group_sends_since_cutoff(slot, cutoff))
except Exception as e:
    print("import error", e)
    import traceback; traceback.print_exc()
'''


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not PASSWORD:
        raise SystemExit("Set VPS_PASSWORD")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    _, stdout, stderr = c.exec_command(f"python3 - <<'PY'\n{REMOTE}\nPY", timeout=300)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    c.close()
    path = os.path.join(os.environ.get("TEMP", "."), "posting_deep_dive.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
        if err.strip():
            f.write("\n\nSTDERR:\n" + err)
    print(out)
    if err.strip():
        print("STDERR:", err[:3000], file=sys.stderr)
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
