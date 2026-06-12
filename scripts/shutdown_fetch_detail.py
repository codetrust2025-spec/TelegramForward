#!/usr/bin/env python3
"""Fetch shutdown source + per-account runtime evidence from VPS."""
from __future__ import annotations

import json
import os
import sys

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
ROOT = "/opt/telegramforward.old"


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 120) -> str:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if code != 0 and not out.strip():
        raise RuntimeError(f"exit {code}: {err[:1500]}")
    return out + (f"\n[stderr]\n{err}" if err.strip() else "")


REMOTE_PY = r'''
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/opt/telegramforward.old")
shutdown = json.loads((ROOT / "data/account_shutdown.json").read_text())
slots = ["account1", "account2", "account4", "account8"]
NO_POST = int(os.environ.get("ACCOUNT_NO_POST_SHUTDOWN_SECONDS", "43200"))
DUR = int(os.environ.get("ACCOUNT_SHUTDOWN_DURATION_SECONDS", str(7 * 86400)))
now = time.time()

def iso(ts):
    if not ts:
        return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()

print(json.dumps({"NO_POST_SECONDS": NO_POST, "DURATION_SECONDS": DUR, "now": now, "now_iso": iso(now)}, indent=2))

for s in slots:
    rec = shutdown.get(s, {})
    st = {}
    for name in [f"worker_state_{s}.json", f"account_state_{s}.json", f"state_{s}.json"]:
        p = ROOT / "data" / name
        if p.exists():
            st = json.loads(p.read_text())
            st["_file"] = name
            break
    ds = {}
    dp = ROOT / "data" / f"daily_stats_{s}.json"
    if dp.exists():
        ds = json.loads(dp.read_text())
    ss = {}
    sp = ROOT / "data" / f"send_stats_{s}.json"
    if sp.exists():
        ss = json.loads(sp.read_text())

    last_send = rec.get("last_send_at") or st.get("last_success_at") or st.get("last_send_at") or ss.get("last_success_at")
    last_fail = st.get("last_fail_at") or ss.get("last_fail_at")
    idle = (now - float(last_send)) if last_send else None

    out = {
        "slot": s,
        "shutdown_record": rec,
        "shutdown_at_iso": iso(rec.get("shutdown_at")),
        "resume_at_iso": iso(rec.get("resume_at")),
        "last_send_at": last_send,
        "last_send_iso": iso(last_send),
        "last_fail_at": last_fail,
        "last_fail_iso": iso(last_fail),
        "idle_seconds": idle,
        "idle_hours": round(idle / 3600, 2) if idle is not None else None,
        "NO_POST_SECONDS": NO_POST,
        "idle_ge_threshold": idle is not None and idle >= NO_POST,
        "reason": rec.get("reason"),
        "worker_state_file": st.get("_file"),
        "success": st.get("success"),
        "failed": st.get("failed"),
        "running": st.get("running"),
        "messages_sent_24h": st.get("messages_sent_24h"),
        "forwarded_since_reset": st.get("forwarded_since_reset"),
        "stats_reset_at": st.get("stats_reset_at"),
        "stats_reset_iso": iso(st.get("stats_reset_at")),
        "success_list_tail": (st.get("success_list") or [])[-3:],
        "failed_list_tail": (st.get("failed_list") or [])[-3:],
        "daily_stats": ds,
        "send_stats": ss,
    }
    print("ACCOUNT_JSON:" + json.dumps(out))
'''


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not PASSWORD:
        raise SystemExit("Set VPS_PASSWORD")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    for rel in ["core/account_shutdown.py", "core/account_shutdown_monitor.py", "data/account_shutdown.json"]:
        print(f"\n{'='*20} {rel} {'='*20}\n")
        print(run(client, f"cat {ROOT}/{rel}"))

    print(f"\n{'='*20} RUNTIME {'='*20}\n")
    print(run(client, f"python3 - <<'PY'\n{REMOTE_PY}\nPY"))

    print(f"\n{'='*20} SHUTDOWN LOGS {'='*20}\n")
    print(
        run(
            client,
            "grep -iE 'Auto-shutdown|auto-shutdown|shutdown_monitor|no_post|Account auto-shutdown' "
            "/root/.pm2/logs/telegram-backend-out.log 2>/dev/null | tail -50",
        )
    )

    print(f"\n{'='*20} SERVER STARTUP MONITOR {'='*20}\n")
    print(run(client, f"grep -n 'AccountShutdownMonitor\\|shutdown_monitor' {ROOT}/server.py"))

    client.close()


if __name__ == "__main__":
    main()
