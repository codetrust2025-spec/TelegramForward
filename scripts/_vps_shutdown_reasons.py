"""Print shutdown list reasons from VPS."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"


def fmt_ts(ts):
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(ts)


def main() -> int:
    if not PWD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1
    import paramiko

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    path = f"{REMOTE}/data/account_shutdown.json"
    _, o, _ = c.exec_command(f"test -f {path} && cat {path} || echo '{{}}'", timeout=20)
    raw = o.read().decode()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(raw[:2000])
        return 1
    accounts = data.get("accounts") or {}
    _, o2, _ = c.exec_command("curl -s http://127.0.0.1:8000/state", timeout=45)
    state = json.loads(o2.read().decode())
    info = state.get("account_info") or {}

    print(f"=== account_shutdown.json ({len(accounts)} entries) ===\n")
    for slot, row in sorted(accounts.items()):
        name = (info.get(slot) or {}).get("name") or slot
        reason = row.get("reason", "?")
        last = row.get("last_send_at")
        print(f"{slot} — {name}")
        print(f"  reason: {reason}")
        print(f"  shutdown_at: {fmt_ts(row.get('shutdown_at'))}")
        print(f"  resume_at:   {fmt_ts(row.get('resume_at'))}")
        print(f"  last_send_at: {fmt_ts(last)}")
        print(f"  was_running: {row.get('was_running')}")
        print()
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
