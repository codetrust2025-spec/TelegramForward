#!/usr/bin/env python3
"""Read per-account output metrics to decide campaign vs forwarding."""
import json
import os
import socket
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")

script = r'''
import json, os, glob
from datetime import datetime, timezone
from core.account_info_store import load_account_info
from core.posting_mode import load_posting_mode
from core.message_store import load_message_for_account

def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def ts_fmt(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(ts)

results = []
for i in range(1, 11):
    slot = f"account{i}"
    base = f"/opt/telegramforward.old/data/accounts/{slot}"
    info = load_account_info(slot)
    if not info or not info.get("phone"):
        continue
    pm = load_posting_mode(slot)
    msg = (load_message_for_account(slot) or "").strip()
    msg_lines = [ln.strip() for ln in msg.splitlines() if ln.strip()]
    msg_head = " | ".join(msg_lines[:2])[:120] if msg_lines else "(empty)"

    gh = read_json(os.path.join(base, "groups_health.json")) or {}
    groups = gh.get("groups") or gh if isinstance(gh, dict) else {}
    if isinstance(groups, dict):
        glist = list(groups.values()) if groups and isinstance(next(iter(groups.values()), None), dict) else []
    else:
        glist = []
    blocked = sum(1 for g in glist if isinstance(g, dict) and g.get("blocked"))
    total_g = len(glist) if glist else int(info.get("joined_groups") or 0)

    hist = read_json(os.path.join(base, "group_send_history.json")) or {}
    sends = hist.get("sends") or hist.get("history") or []
    if isinstance(sends, dict):
        sends = list(sends.values())
    recent_sends = [s for s in sends if isinstance(s, dict)][-20:]
    send_ok = sum(1 for s in recent_sends if s.get("status") in ("sent", "ok", "success") or s.get("ok"))
    send_fail = len(recent_sends) - send_ok

    cycle = read_json(os.path.join(base, "cycle_metrics_last.json")) or {}
    last_cycle = cycle.get("last_cycle") or cycle

    fwd = pm.forwarding
    row = {
        "slot": slot,
        "display_name": info.get("display_name") or info.get("name"),
        "current_mode": pm.mode,
        "campaign_enabled": pm.campaign_enabled,
        "forwarding_enabled": pm.forwarding_enabled,
        "message_head": msg_head,
        "message_chars": len(msg),
        "forward_source": f"{fwd.source_peer}/{fwd.source_message_id}" if fwd.source_peer else None,
        "joined_groups": int(info.get("joined_groups") or 0),
        "groups_in_health": total_g,
        "groups_blocked": blocked,
        "groups_unblocked": max(0, total_g - blocked),
        "recent_send_samples": len(recent_sends),
        "recent_send_ok": send_ok,
        "recent_send_fail": send_fail,
        "last_send_at": ts_fmt(hist.get("last_send_at") or (recent_sends[-1].get("at") if recent_sends else None)),
        "last_cycle": {
            "sent": last_cycle.get("sent") or last_cycle.get("groups_sent"),
            "skipped": last_cycle.get("skipped") or last_cycle.get("groups_skipped"),
            "failed": last_cycle.get("failed") or last_cycle.get("groups_failed"),
            "mode": last_cycle.get("mode") or last_cycle.get("feature"),
        } if last_cycle else {},
    }
    results.append(row)

print(json.dumps(results, ensure_ascii=False, indent=2))
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmd = f"cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{script}\nPY"
_, stdout, stderr = c.exec_command(cmd, timeout=120)
out = stdout.read().decode(errors="replace")
err = stderr.read().decode(errors="replace")
if err.strip():
    print("ERR:", err, file=sys.stderr)
print(out)

# Also grep PM2/reload logs for SENT/SKIP per account if available
_, stdout2, _ = c.exec_command(
    "grep -h 'account[0-9].*SENT\\|account[0-9].*SKIP\\|cycle.*account' /opt/telegramforward.old/data/reload.log 2>/dev/null | tail -80",
    timeout=30,
)
log_tail = stdout2.read().decode(errors="replace")
if log_tail.strip():
    print("\n=== RECENT LOG TAIL ===")
    print(log_tail)
c.close()
