#!/usr/bin/env python3
import os, socket
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
import json, os, sys, inspect
from pathlib import Path
ROOT = Path("/opt/telegramforward.old")
sys.path.insert(0, str(ROOT)); os.chdir(ROOT)

# grep account_worker for skip/fail outcomes
from core import account_worker as aw
src = Path("core/account_worker.py").read_text()

# Find record_send calls and skip paths
lines = src.splitlines()
for i, ln in enumerate(lines):
    low = ln.lower()
    if any(k in low for k in ["skip", "failed", "record_send", "still_latest", "message_recent", "flood", "sleep"]):
        if "def " in ln or "skip" in low or "fail" in low or "record_send" in low:
            print(f"{i+1}: {ln.rstrip()}")

print("\n=== groups_health account1 (sample) ===")
gh = json.loads((ROOT/"data/accounts/account1/groups_health.json").read_text())
if isinstance(gh, dict):
    for k,v in list(gh.items())[:3]:
        print(k, json.dumps(v)[:400])

print("\n=== groups_health account4 unhealthy ===")
gh4 = json.loads((ROOT/"data/accounts/account4/groups_health.json").read_text())
bad = []
if isinstance(gh4, dict):
    for k,v in gh4.items():
        if isinstance(v, dict) and (v.get("consecutive_failures",0) > 0 or v.get("health_score",1) < 0.5 or v.get("blocked")):
            bad.append((k, v))
print(f"unhealthy groups: {len(bad)}")
for k,v in bad[:8]:
    print(f"  {k}: score={v.get('health_score')} fails={v.get('consecutive_failures')} last_err={str(v.get('last_error',''))[:120]}")

print("\n=== groups_health account8 ===")
gh8 = json.loads((ROOT/"data/accounts/account8/groups_health.json").read_text())
bad8 = []
if isinstance(gh8, dict):
    for k,v in gh8.items():
        if isinstance(v, dict):
            bad8.append((k, v.get("health_score"), v.get("consecutive_failures"), str(v.get("last_error",""))[:80]))
print(f"total groups: {len(gh8)}")
for row in sorted(bad8, key=lambda x: x[1] or 0)[:10]:
    print(f"  {row[0]}: score={row[1]} fails={row[2]} err={row[3]}")

# account8 message.txt exists?
for s in ["account8","account4","account1"]:
    mp = ROOT/f"data/accounts/{s}/message.txt"
    print(f"\n{s} message.txt exists={mp.exists()}", f"size={mp.stat().st_size}" if mp.exists() else "")

# join_state for account4/8
for s in ["account4","account8"]:
    js = ROOT/f"data/accounts/{s}/join_state.json"
    if js.exists():
        d = json.loads(js.read_text())
        print(f"\n{s} join_state keys: {list(d.keys())[:10]}")
        print(json.dumps(d, indent=2)[:1500])

# account_info
for s in ["account1","account2","account4","account8"]:
    ai = ROOT/f"data/accounts/{s}/account_info.json"
    if ai.exists():
        d = json.loads(ai.read_text())
        print(f"\n{s} account_info: display={d.get('display_name')} name={d.get('name')} enabled={d.get('enabled')} groups={d.get('group_count') or d.get('groups_count')}")

# Check .running_workers at shutdown - was account4 in list when shutdown happened?
# Search reload.log for account4 shutdown
rl = (ROOT/"data/reload.log").read_text()
for ln in rl.splitlines():
    if "account4" in ln or "account8" in ln:
        if "shutdown" in ln.lower() or "resume" in ln.lower() or "running workers" in ln.lower():
            print("RL:", ln)

# cycle metrics history - any other files?
for s in ["account4","account8"]:
    d = ROOT/f"data/accounts/{s}"
    for f in sorted(d.glob("cycle*")):
        print(f"{s} {f.name} size={f.stat().st_size}")

# Search PM2 error log for account4/8 failures
import subprocess
for s in ["account4","account8"]:
    r = subprocess.run(
        ["grep", "-E", f"(account{s[-1]}|{s}).*(fail|error|Flood|banned|skip|sleep)", "/root/.pm2/logs/telegram-backend-error.log"],
        capture_output=True, text=True
    )
    lines = (r.stdout or "").strip().splitlines()
    print(f"\nPM2 error log {s}: {len(lines)} matches")
    for ln in lines[-15:]:
        print(" ", ln[:200])
'''

script = f"cd /opt/telegramforward.old && ./venv/bin/python3 - <<'PY'\n{REMOTE}\nPY"
out = run(script, timeout=180)
path = os.path.join(os.environ.get("TEMP","."), "worker_fail_paths.txt")
open(path,"w",encoding="utf-8").write(out)
print(out[:12000])
print(f"\n... saved full to {path}")
