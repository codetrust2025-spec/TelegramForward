#!/usr/bin/env python3
"""Fetch group_send_history, cycle_metrics, backups for shutdown RCA."""
import os, socket, json, datetime
import paramiko

PASSWORD = os.environ.get("VPS_PASSWORD", "")

def run(cmd, timeout=180):
    sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
    t = paramiko.Transport(sock)
    t.connect(username="root", password=PASSWORD)
    ch = t.open_session()
    ch.settimeout(timeout)
    ch.exec_command(cmd)
    out = b""
    while True:
        if ch.recv_ready():
            out += ch.recv(65535)
        if ch.exit_status_ready():
            while ch.recv_ready():
                out += ch.recv(65535)
            break
    t.close()
    return out.decode("utf-8", errors="replace")

REMOTE = r'''
import json, os, sys
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path("/opt/telegramforward.old")
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)

SLOTS = ["account1","account2","account4","account8"]
BACKUP = ROOT / "backups/pre_update_20260531_121134/data/accounts"

def ts_fmt(t):
    if not t: return "null"
    return datetime.fromtimestamp(float(t), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def analyze_group_history(path, label):
    print(f"\n--- {label} ---")
    if not Path(path).exists():
        print("  MISSING")
        return
    data = json.loads(Path(path).read_text())
    events = data if isinstance(data, list) else data.get("events", data.get("history", []))
    if isinstance(data, dict) and not events:
        # maybe dict keyed by group
        print(f"  keys: {list(data.keys())[:20]}")
        print(f"  sample: {str(data)[:800]}")
        return
    print(f"  event count: {len(events)}")
    if events:
        last = max(events, key=lambda e: float(e.get("t") or e.get("ts") or 0))
        print(f"  last event: t={ts_fmt(last.get('t') or last.get('ts'))} group={last.get('group') or last.get('group_id')} status={last.get('status') or last.get('result')}")
        # count by status/reason in last 50
        from collections import Counter
        recent = sorted(events, key=lambda e: float(e.get("t") or e.get("ts") or 0))[-50:]
        reasons = Counter()
        for e in recent:
            r = e.get("status") or e.get("result") or e.get("reason") or "unknown"
            reasons[r] += 1
        print(f"  last 50 outcomes: {dict(reasons)}")

for s in SLOTS:
    print(f"\n{'='*60}\n{s}\n{'='*60}")
    analyze_group_history(ROOT/f"data/accounts/{s}/group_send_history.json", "live group_send_history")
    analyze_group_history(BACKUP/s/"group_send_history.json", "backup 20260531_121134 group_send_history")
    
    cm = ROOT / f"data/accounts/{s}/cycle_metrics_last.json"
    if cm.exists():
        print(f"\n--- cycle_metrics_last.json ---")
        d = json.loads(cm.read_text())
        print(json.dumps(d, indent=2)[:3000])
    
    sh = ROOT / f"data/accounts/{s}/send_history.json"
    if sh.exists():
        print(f"\n--- send_history (live) ---")
        print(sh.read_text()[:500])
    
    # shutdown record
    sd = json.loads((ROOT/"data/account_shutdown.json").read_text())
    rec = sd.get("accounts",{}).get(s) or sd.get(s)
    if rec:
        print(f"\n--- shutdown record ---")
        print(json.dumps(rec, indent=2))

# reload.log around shutdown times
print("\n\n=== reload.log tail (last 80 lines) ===")
rl = ROOT / "data/reload.log"
if rl.exists():
    lines = rl.read_text().splitlines()
    for ln in lines[-80:]:
        print(ln)

# account_expected_to_post check at shutdown time - read running_workers history from reload
print("\n=== Auto-resume mentions per account ===")
text = rl.read_text() if rl.exists() else ""
for s in SLOTS:
    cnt = text.count(f'"{s}"') + text.count(f"'{s}'")
    resume = sum(1 for ln in text.splitlines() if "Auto-resumed" in ln and s in ln)
    print(f"  {s}: reload mentions={cnt}, auto-resume lines={resume}")

# groups_health summary
for s in SLOTS:
    gh = ROOT / f"data/accounts/{s}/groups_health.json"
    if gh.exists():
        d = json.loads(gh.read_text())
        total = len(d) if isinstance(d, dict) else len(d)
        blocked = sum(1 for v in (d.values() if isinstance(d,dict) else d) if isinstance(v,dict) and v.get("blocked"))
        risky = sum(1 for v in (d.values() if isinstance(d,dict) else d) if isinstance(v,dict) and v.get("risky"))
        print(f"\n{s} groups_health: total={total} blocked={blocked} risky={risky}")

# Check account_shutdown evaluate - was worker running?
from core.account_shutdown import account_expected_to_post
for s in SLOTS:
    print(f"{s} expected_to_post NOW: {account_expected_to_post(s)}")
'''

script = f"cd /opt/telegramforward.old && ./venv/bin/python3 - <<'PY'\n{REMOTE}\nPY"
out = run(script, timeout=180)
path = os.path.join(os.environ.get("TEMP","."), "group_send_deep.txt")
open(path,"w",encoding="utf-8").write(out)
print(out)
