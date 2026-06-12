#!/usr/bin/env python3
"""Deep diagnostic: why campaign posting is not happening."""
from __future__ import annotations

import json
import socket
import sys

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = "8897870998s@SS"

DIAG = r'''
import json, os, sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/opt/telegramforward.old")
STATE = ROOT / "data" / "state"
CAMPAIGN = ["account3", "account5", "account7", "account8", "account10"]

def read_json(p, default=None):
    try:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"_error": str(e)}
    return default

print("=" * 60)
print("CAMPAIGN ACCOUNT RUNTIME")
print("=" * 60)
from services.account_manager import manager
from core.posting_mode import load_posting_mode
from core.message_store import load_message_for_account

ui = manager.build_ui_state()
st = ui.get("account_states") or {}
modes = ui.get("posting_modes") or {}

for slot in CAMPAIGN:
    a = st.get(slot) or {}
    pm = load_posting_mode(slot)
    msg = (load_message_for_account(slot) or "")[:60].replace("\n", " ")
    print(f"\n--- {slot} ---")
    print(f"  running={a.get('running')} campaign_running={a.get('campaign_running')} status={a.get('status')}")
    print(f"  next_cycle_in={a.get('next_cycle_in')} notification={str(a.get('notification') or '')[:120]}")
    print(f"  mode={pm.mode} campaign={pm.campaign_enabled} forwarding={pm.forwarding_enabled}")
    print(f"  success={a.get('success')} failed={a.get('failed')} cycle={a.get('cycle')}")
    print(f"  current_group={a.get('current_group')!r}")
    print(f"  message: {msg}...")
    camp = a.get("campaign") or {}
    if camp:
        print(f"  campaign state: active={camp.get('active_groups')} tick={camp.get('tick_processed')}/{camp.get('tick_total')}")

print("\n" + "=" * 60)
print("GROUP HEALTH & LAST CYCLE")
print("=" * 60)
for slot in CAMPAIGN:
    gh = read_json(STATE / slot / "groups_health.json", {})
    cm = read_json(STATE / slot / "cycle_metrics_last.json", {})
    healthy = sum(1 for g in (gh.get("groups") or []) if g.get("status") in ("healthy", "cooling"))
    blocked = sum(1 for g in (gh.get("groups") or []) if g.get("status") == "blocked")
    print(f"\n{slot}: healthy/cooling={healthy} blocked={blocked} total_groups={len(gh.get('groups') or [])}")
    if cm:
        print(f"  last_cycle: success={cm.get('success')} fail={cm.get('failed')} skip={cm.get('skipped')} reason={cm.get('end_reason')}")

print("\n" + "=" * 60)
print("RECENT SEND HISTORY (last 5 events per account)")
print("=" * 60)
for slot in CAMPAIGN:
    hist = read_json(STATE / slot / "group_send_history.json", [])
    if isinstance(hist, list):
        events = hist[-5:]
    elif isinstance(hist, dict):
        events = list(hist.values())[-5:] if hist else []
    else:
        events = []
    print(f"\n{slot}:")
    for e in events:
        if isinstance(e, dict):
            print(f"  {e.get('ts','?')[:19]} {e.get('group','?')[:40]} -> {e.get('result', e.get('status','?'))} {str(e.get('reason',''))[:50]}")

print("\n" + "=" * 60)
print("RECENT WORKER LOGS (campaign keywords)")
print("=" * 60)
import subprocess
r = subprocess.run(
    ["pm2", "logs", "telegram-backend", "--lines", "200", "--nostream"],
    capture_output=True, text=True, timeout=30,
)
lines = (r.stdout + r.stderr).splitlines()
keywords = ("SEND_FAIL", "appledeveloper", "skip", "no_post", "cant_write", "flood", "campaign", "blocked", "shutdown", "already")
for line in lines[-200:]:
    ll = line.lower()
    if any(k in ll for k in keywords):
        # trim pm2 prefix noise
        if "|telegram |" in line:
            line = line.split("|telegram |", 1)[-1]
        print(line[:200])
'''

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, username=USER, password=PASSWORD, sock=sock)
    _, stdout, stderr = client.exec_command(
        f"cd /opt/telegramforward.old && set -a && . ./.env && set +a && "
        f"PYTHONPATH=. ./venv/bin/python - <<'PY'\n{DIAG}\nPY",
        timeout=120,
    )
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print("STDERR:", err[-4000:], file=sys.stderr)
    client.close()


if __name__ == "__main__":
    main()
