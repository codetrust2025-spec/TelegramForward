#!/usr/bin/env python3
import json, os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")

script = r'''
import json, os
from datetime import datetime, timezone
from core.account_info_store import load_account_info
from core.posting_mode import load_posting_mode

def read_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def ts(ts):
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return None

def health_counts(slot):
    gh = read_json(f"/opt/telegramforward.old/data/accounts/{slot}/groups_health.json") or {}
    counts = gh.get("counts") if isinstance(gh.get("counts"), dict) else {}
    if not counts:
        # legacy flat map
        blocked = healthy = 0
        for k, v in gh.items():
            if isinstance(v, dict) and "blocked" in v:
                if v.get("blocked"):
                    blocked += 1
                else:
                    healthy += 1
        return {"blocked": blocked, "healthy": healthy, "assigned": blocked + healthy}
    return counts

def send_events(slot, limit=500):
    hist = read_json(f"/opt/telegramforward.old/data/accounts/{slot}/group_send_history.json") or {}
    ev = hist.get("events") or []
    if not isinstance(ev, list):
        return []
    return ev[-limit:]

rows = []
for i in range(1, 11):
    slot = f"account{i}"
    info = load_account_info(slot)
    if not info:
        continue
    pm = load_posting_mode(slot)
    hc = health_counts(slot)
    ev = send_events(slot)
    last_ev = ev[-1] if ev else None
    cycle = read_json(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json") or {}

    # infer historical mode at last cycle from posting_mode backup or cycle feature
    cycle_success = int(cycle.get("success") or 0)
    cycle_failed = int(cycle.get("failed") or 0)
    cycle_skipped = int(cycle.get("skipped") or 0)
    cycle_total = int(cycle.get("groups_total") or 0)

    rows.append({
        "slot": slot,
        "display": info.get("display_name") or info.get("name"),
        "mode_now": pm.mode,
        "joined_groups": info.get("joined_groups"),
        "health": hc,
        "send_events_total": len(ev),
        "last_send_event": ts(last_ev.get("t") if last_ev else None),
        "last_send_group": (last_ev or {}).get("g"),
        "last_cycle": {
            "success": cycle_success,
            "failed": cycle_failed,
            "skipped": cycle_skipped,
            "total": cycle_total,
            "success_rate": cycle.get("success_rate"),
            "ended_early": cycle.get("ended_early"),
            "end_reason": cycle.get("end_reason"),
        },
    })

print(json.dumps(rows, ensure_ascii=False, indent=2))
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmd = f"cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{script}\nPY"
_, stdout, _ = c.exec_command(cmd, timeout=120)
print(stdout.read().decode(errors="replace"))
c.close()
