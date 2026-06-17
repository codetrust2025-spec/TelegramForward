#!/usr/bin/env python3
"""Upload fleet restart script to VPS and run in background."""
from __future__ import annotations

import os
import socket
import sys
import time

import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"

SCRIPT = r'''#!/usr/bin/env python3
import json, subprocess, sys, time, urllib.request
sys.path.insert(0, "/opt/telegramforward.old")

from core.dashboard_auth_vps import get_credentials, create_session_token, SESSION_COOKIE
from core.posting_mode import load_posting_mode
from core.account_info_store import load_account_info
from core.worker_persistence import load_running_slots
from core.daily_stats import compute_daily_stats

FORWARD = ["account1", "account2", "account4", "account6", "account9"]
CAMPAIGN = ["account3", "account5", "account7", "account8", "account10"]
ACTIVE = FORWARD + CAMPAIGN

user, _ = get_credentials()
token = create_session_token(user, role="admin")

def api(method, path, timeout=25):
    req = urllib.request.Request("http://127.0.0.1:8000" + path, method=method, data=b"" if method == "POST" else None)
    req.add_header("Cookie", f"{SESSION_COOKIE}={token}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())

def log(msg):
    print(msg, flush=True)

log("=== Diagnosis ===")
running = set(load_running_slots())
for slot in ACTIVE:
    info = load_account_info(slot) or {}
    pm = load_posting_mode(slot)
    role = "FWD" if slot in FORWARD else "CAMP"
    log(f"{slot} [{role}] logged={bool(info.get('phone'))} was_running={slot in running} mode={pm.mode}")

log("\n=== Session errors (recent) ===")
r = subprocess.run(
    ["bash", "-lc", "pm2 logs telegram-backend --lines 250 --nostream 2>&1 | grep -iE 'wrong session|connection failed|authkey|not logged' | tail -15"],
    capture_output=True, text=True, timeout=30,
)
for line in (r.stdout or "").splitlines():
    log(line[:220])

ds = compute_daily_stats(ACTIVE)
g = ds.get("global") or {}
log(f"\nPosts today before: fwd={g.get('forward_posts')} camp={g.get('campaign_posts')}")

log("\n=== Stop all ===")
try:
    log(str(api("POST", "/stop", timeout=30)))
except Exception as e:
    log(f"stop: {e}")
time.sleep(2)

log("\n=== Start all logged-in ===")
try:
    log(str(api("POST", "/start", timeout=15)))
except Exception as e:
    log(f"start queue: {e}")

log("Waiting 25s for workers...")
time.sleep(25)

log("\n=== Running slots after start ===")
for slot in ACTIVE:
    log(f"  {slot}: {slot in set(load_running_slots())}")

log("\n=== Recent activity log ===")
r2 = subprocess.run(
    ["bash", "-lc", "pm2 logs telegram-backend --lines 120 --nostream 2>&1 | grep -iE 'Worker started|Connection failed|wrong session|Forward|tick|Cycle started' | tail -20"],
    capture_output=True, text=True, timeout=30,
)
for line in (r2.stdout or "").splitlines():
    log(line[:220])

ds2 = compute_daily_stats(ACTIVE)
g2 = ds2.get("global") or {}
log(f"\nPosts today after: fwd={g2.get('forward_posts')} camp={g2.get('campaign_posts')}")
log("DONE")
'''

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    sftp = c.open_sftp()
    with sftp.file("/tmp/fleet_restart_run.py", "w") as f:
        f.write(SCRIPT)
    sftp.close()
    c.exec_command(f"chmod +x /tmp/fleet_restart_run.py")
    c.exec_command(f"rm -f /tmp/fleet_restart.out")
    c.exec_command(
        f"cd {REMOTE} && source venv/bin/activate && nohup python3 /tmp/fleet_restart_run.py > /tmp/fleet_restart.out 2>&1 &"
    )
    print("Started background restart on VPS, polling log...")
    for i in range(24):
        time.sleep(5)
        _, stdout, _ = c.exec_command("cat /tmp/fleet_restart.out 2>/dev/null", timeout=15)
        text = stdout.read().decode("utf-8", errors="replace")
        if "DONE" in text:
            print(text)
            break
        if i % 3 == 2:
            print(f"... still running ({(i+1)*5}s)")
    else:
        _, stdout, _ = c.exec_command("tail -80 /tmp/fleet_restart.out 2>/dev/null", timeout=15)
        print(stdout.read().decode("utf-8", errors="replace"))
    c.close()

if __name__ == "__main__":
    main()
