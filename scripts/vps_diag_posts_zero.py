#!/usr/bin/env python3
from __future__ import annotations

import socket
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward.old"

ANALYZE = r"""
import json, sys
from pathlib import Path
d = json.load(sys.stdin)
ds = d.get("daily_stats", {})
print("=== DAILY STATS ===")
print("window", ds.get("window"), "reset_at", ds.get("reset_at"))
g = ds.get("global", {})
print("global forward_posts", g.get("forward_posts"), "campaign_posts", g.get("campaign_posts"), "forwarded", g.get("forwarded"))
print("\n=== ALL ACCOUNTS ===")
for slot in sorted(d.get("account_states", {})):
    a = d["account_states"][slot]
    f = a.get("forwarding") or {}
    c = a.get("campaign") or {}
    row = ds.get("per_account", {}).get(slot, {})
    print(f"{slot} run={a.get('running')} fwd={a.get('forwarding_running')} camp={a.get('campaign_running')} tick_ok={f.get('success',0)} skip={f.get('skipped_already_posted',0)} fail={f.get('failed',0)} total={f.get('active_groups',0)} camp_ok={c.get('success',0)} fwd24h={a.get('forward_posts_24h',0)} daily_fwd={row.get('forward_posts')} health={round(float(a.get('health_score') or 0),1)}")
print("\n=== SEND HISTORY ===")
root = Path("/opt/telegramforward.old/data/accounts")
for slot in sorted(d.get("account_states", {})):
    base = root / slot
    parts = []
    for name in ("send_history_forward.json", "send_history.json", "send_history_campaign.json"):
        p = base / name
        if not p.exists():
            continue
        data = json.loads(p.read_text())
        ts = data.get("timestamps") if isinstance(data, dict) else None
        n = len(ts) if isinstance(ts, list) else (len(data) if isinstance(data, list) else len(data))
        parts.append(f"{name}={n}")
    if parts:
        print(slot, " ".join(parts))
print("\n=== FORWARD LOGS ===")
for slot in sorted(d.get("account_states", {})):
    a = d["account_states"][slot]
    if not a.get("forwarding_running"):
        continue
    print("---", slot, "---")
    print("notif:", (a.get("notification") or "")[:140])
    for L in (a.get("logs") or [])[-12:]:
        msg = (L.get("summary") or L.get("msg") or (L.get("fields") or {}).get("detail") or "")[:120]
        print(" ", L.get("event") or "", L.get("action") or "", L.get("level") or "", msg)
"""

def main():
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username="root", password=PASSWORD, sock=sock)
    sftp = c.open_sftp()
    with sftp.file("/tmp/diag_posts.py", "w") as f:
        f.write(ANALYZE)
    sftp.close()
    cmd = (
        "curl -s -c /tmp/cj -b /tmp/cj -X POST http://127.0.0.1:8000/auth/login "
        "-H 'Content-Type: application/json' "
        "-d '{\"username\":\"admin\",\"password\":\"734720077743\"}' > /dev/null && "
        "curl -s -b /tmp/cj http://127.0.0.1:8000/state | python3 /tmp/diag_posts.py"
    )
    _, stdout, stderr = c.exec_command(cmd, timeout=120)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("STDERR:", err)
    c.close()

if __name__ == "__main__":
    main()
