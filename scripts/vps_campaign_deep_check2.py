#!/usr/bin/env python3
"""Deep check via API + data files + pm2 logs."""
from __future__ import annotations

import json
import socket
import sys

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = "REMOVED_VPS_PASSWORD"

REMOTE = r'''
import json, os, sys, urllib.request, http.cookiejar
from pathlib import Path

ROOT = Path("/opt/telegramforward.old")
CAMPAIGN = ["account3", "account5", "account7", "account8", "account10"]

# API state from live PM2 process
pw = ""
for line in (ROOT / ".env").read_text().splitlines():
    if line.startswith("DASHBOARD_PASSWORD="):
        pw = line.split("=", 1)[1].strip().strip('"').strip("'")
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def api(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"http://127.0.0.1:8000{path}", data=data,
        headers={"Content-Type": "application/json"} if data else {}, method=method)
    with op.open(req, timeout=30) as r:
        return json.loads(r.read().decode())
api("POST", "/auth/login", {"username": "admin", "password": pw})
state = api("GET", "/state")
st = state.get("account_states") or {}

print("=== LIVE API STATE (campaign) ===")
for slot in CAMPAIGN:
    a = st.get(slot) or {}
    mg = a.get("my_groups") or []
    camp = a.get("campaign") or {}
    print(f"\n{slot}:")
    print(f"  running={a.get('running')} campaign_running={a.get('campaign_running')} status={a.get('status')}")
    print(f"  success={a.get('success')} failed={a.get('failed')} cycle={a.get('cycle')}")
    print(f"  current_group={a.get('current_group')!r}")
    print(f"  notification={str(a.get('notification') or '')[:150]}")
    print(f"  my_groups count={len(mg)} active_groups={camp.get('active_groups')} tick={camp.get('tick_processed')}/{camp.get('tick_total')}")
    print(f"  health_score={a.get('health_score')} heavy_rate_limit={a.get('heavy_rate_limit')}")

print("\n=== GROUPS LIST FILES ===")
for slot in CAMPAIGN:
    for name in ["groups.txt", "groups.json", "joined_groups.json"]:
        p = ROOT / "data" / "accounts" / slot / name
        if p.exists():
            print(f"  {slot}/{name}: {p.stat().st_size} bytes")
    gl = ROOT / "data" / "state" / slot / "groups_health.json"
    if gl.exists():
        gh = json.loads(gl.read_text(encoding="utf-8"))
        groups = gh.get("groups") or []
        from collections import Counter
        c = Counter(g.get("status") for g in groups)
        print(f"  {slot} health: {dict(c)} total={len(groups)}")

print("\n=== SHUTDOWN STATUS ===")
sh = state.get("account_shutdown") or {}
for slot in CAMPAIGN:
    s = sh.get(slot)
    if s:
        print(f"  {slot}: {s}")

print("\n=== PM2 LOGS (last 300, filtered) ===")
import subprocess
r = subprocess.run(["pm2", "logs", "telegram-backend", "--lines", "300", "--nostream"],
    capture_output=True, text=True, timeout=45)
for line in (r.stdout + r.stderr).splitlines():
    ll = line.lower()
    if any(k in ll for k in ["send_fail", "appledeveloper", "account3", "account5", "account7", "account8", "account10",
                             "skip", "no_post", "cant_write", "flood", "campaign", "already_posted", "shutdown", "error", "fail"]):
        if "|telegram |" in line:
            line = line.split("|telegram |", 1)[-1].strip()
        print(line[:220])

print("\n=== RECENT group_send_history ===")
for slot in CAMPAIGN:
    p = ROOT / "data" / "state" / slot / "group_send_history.json"
    if not p.exists():
        print(f"{slot}: no history file")
        continue
    raw = json.loads(p.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else list(raw.values()) if isinstance(raw, dict) else []
    recent = items[-3:] if items else []
    print(f"{slot} ({len(items)} total events):")
    for e in recent:
        if isinstance(e, dict):
            print(f"  {e.get('group','?')[:45]} -> {e.get('result', e.get('status'))} {str(e.get('reason',''))[:60]}")
'''

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username=USER, password=PASSWORD, sock=sock)
    _, stdout, stderr = c.exec_command(
        f"cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE}\nPY",
        timeout=120,
    )
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR:", err[-3000:])
    c.close()

if __name__ == "__main__":
    main()
