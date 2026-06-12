#!/usr/bin/env python3
import os, socket, paramiko, json

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
import json
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path("/opt/telegramforward.old")

for slot in ["account1", "account2"]:
    gh = json.loads((ROOT/f"data/accounts/{slot}/groups_health.json").read_text())
    print(f"\n{'='*50}\n{slot} groups_health counts: {gh.get('counts')}")
    detail = gh.get("detail", {})
    results = {}
    for g, v in detail.items():
        lr = v.get("last_result", "?")
        results[lr] = results.get(lr, 0) + 1
    print(f"last_result breakdown: {results}")
    healthy = gh.get("healthy", [])
    blocked = gh.get("blocked", [])
    risky = gh.get("risky", [])
    cooling = gh.get("cooling", [])
    print(f"healthy={len(healthy)} blocked={len(blocked)} risky={len(risky)} cooling={len(cooling)} assigned={gh.get('assigned_count')}")
    # show groups with last_result != sent/ok
    skip_like = [(g,v) for g,v in detail.items() if v.get("last_result") not in ("sent", "ok", "joined_sent")]
    print(f"non-success last_result groups: {len(skip_like)}")
    from collections import Counter
    c = Counter(v.get("last_result") for g,v in skip_like)
    print(f"  types: {dict(c)}")
    for g,v in list(skip_like)[:5]:
        print(f"  {g}: {v.get('last_result')} processed={datetime.fromtimestamp(v.get('last_processed',0), tz=timezone.utc)}")

    cm = json.loads((ROOT/f"data/accounts/{slot}/cycle_metrics_last.json").read_text())
    print(f"last cycle: #{cm['cycle_number']} groups={cm['groups_total']} ok={cm['success']} fail={cm['failed']} skip={cm['skipped']}")

# account8 - no message.txt?
for slot in ["account8","account4"]:
    mp = ROOT/f"data/accounts/{slot}/message.txt"
    print(f"\n{slot} message.txt: exists={mp.exists()}")
    if mp.exists():
        print(f"  content preview: {mp.read_text()[:200]!r}")

# When account4/8 shutdown logged
import subprocess
r = subprocess.run(["grep", "-E", "account4|account8", "/opt/telegramforward.old/data/reload.log"], capture_output=True, text=True)
for ln in r.stdout.splitlines():
    if "shutdown" in ln.lower() or "auto-shutdown" in ln.lower():
        print("RL:", ln)
'''

script = f"cd /opt/telegramforward.old && ./venv/bin/python3 - <<'PY'\n{REMOTE}\nPY"
out = run(script, timeout=180)
path = os.path.join(os.environ.get("TEMP","."), "account12_health.txt")
open(path, "w", encoding="utf-8").write(out)
print(f"saved {len(out)} chars")
