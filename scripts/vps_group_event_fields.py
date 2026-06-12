#!/usr/bin/env python3
import os, socket, json
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
from collections import Counter
ROOT = Path("/opt/telegramforward.old")
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)

def ts_fmt(t):
    return datetime.fromtimestamp(float(t), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def analyze_events(slot, idle_start, idle_end):
    path = ROOT / f"data/accounts/{slot}/group_send_history.json"
    if not path.exists():
        print(f"{slot}: NO group_send_history")
        return
    data = json.loads(path.read_text())
    events = data if isinstance(data, list) else data.get("events", [])
    print(f"\n{'='*60}\n{slot} — idle window {ts_fmt(idle_start)} to {ts_fmt(idle_end)}\n{'='*60}")
    print(f"Total events: {len(events)}")
    if events:
        print("Sample event keys:", list(events[0].keys()))
        print("Sample event:", json.dumps(events[0], indent=2)[:600])
        print("Sample last event:", json.dumps(events[-1], indent=2)[:600])
    
    # events in idle window
    idle = [e for e in events if idle_start <= float(e.get("t") or 0) <= idle_end]
    print(f"Events IN idle window: {len(idle)}")
    
    # events after last success
    after = [e for e in events if float(e.get("t") or 0) > idle_start]
    print(f"Events AFTER last success: {len(after)}")
    
    for label, subset in [("idle window", idle), ("after last success", after)]:
        if not subset:
            continue
        print(f"\n  -- {label} outcome breakdown --")
        # try various field names
        for field in ["outcome", "result", "status", "action", "reason", "skip_reason"]:
            vals = Counter(str(e.get(field,"")) for e in subset if e.get(field))
            if vals:
                print(f"    {field}: {dict(vals.most_common(15))}")
        # combined key
        combo = Counter()
        for e in subset:
            k = "|".join(str(e.get(f,"")) for f in ["action","reason","outcome","result","status"] if e.get(f))
            combo[k or "empty"] += 1
        print(f"    combo top 15: {dict(combo.most_common(15))}")

# idle windows (unix ts)
windows = {
    "account1": (1780208563, 1780257818),  # last send -> shutdown
    "account2": (1780200422, 1780257818),
    "account4": (1779953903, 1780048247),
}
for s, (start, end) in windows.items():
    analyze_events(s, start, end)

# account4/8 - get failure details from cycle around shutdown
for s in ["account4", "account8"]:
    cm = json.loads((ROOT/f"data/accounts/{s}/cycle_metrics_last.json").read_text())
    print(f"\n{s} last cycle: success={cm['success']} failed={cm['failed']} skipped={cm['skipped']} groups={cm['groups_total']}")
    
# group_intelligence / blocked for account4/8
for s in ["account4", "account8"]:
    bi = ROOT/f"data/accounts/{s}/blocked_groups.json"
    ig = ROOT/f"data/accounts/{s}/invalid_groups.json"
    if bi.exists():
        b = json.loads(bi.read_text())
        print(f"\n{s} blocked_groups count: {len(b) if isinstance(b,(list,dict)) else 0}")
        if isinstance(b, dict):
            for k,v in list(b.items())[:5]:
                print(f"  {k}: {str(v)[:200]}")
    if ig.exists():
        inv = json.loads(ig.read_text())
        print(f"{s} invalid_groups count: {len(inv) if isinstance(inv,(list,dict)) else 0}")

# Read group_send_stats record format
from core import group_send_stats as gs
import inspect
print("\n=== record_group_send source ===")
print(inspect.getsource(gs.record_group_send)[:2000])

# Parse group_send_history events with correct fields after seeing record format
print("\n=== Re-analyze with record_group_send fields ===")
for slot in ["account1", "account2"]:
    path = ROOT / f"data/accounts/{slot}/group_send_history.json"
    events = json.loads(path.read_text())
    if isinstance(events, dict):
        events = events.get("events", [])
    cutoff = 1780200422 if slot == "account2" else 1780208563
    after = [e for e in events if float(e.get("t") or 0) > cutoff]
    print(f"\n{slot}: {len(after)} events after last success")
    if after:
        print("  first after:", json.dumps(after[0], indent=2)[:800])
        print("  last after:", json.dumps(after[-1], indent=2)[:800])
        ok = sum(1 for e in after if e.get("ok"))
        print(f"  ok=true count: {ok}")
        reasons = Counter(e.get("reason") or e.get("skip") or "?" for e in after)
        print(f"  reasons: {dict(reasons.most_common(20))}")
'''

script = f"cd /opt/telegramforward.old && ./venv/bin/python3 - <<'PY'\n{REMOTE}\nPY"
out = run(script, timeout=180)
path = os.path.join(os.environ.get("TEMP","."), "group_event_fields.txt")
open(path, "w", encoding="utf-8").write(out)
print(f"Wrote {len(out)} chars to {path}")
print(out[:8000])
