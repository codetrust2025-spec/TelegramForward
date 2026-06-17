#!/usr/bin/env python3
import json, os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")

script = r'''
import json, os
from datetime import datetime, timezone
from core.account_info_store import load_account_info

def read_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def ts(ts):
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None

shutdown = read_json("/opt/telegramforward.old/data/account_shutdown.json") or {}
accounts_sd = shutdown.get("accounts") or {}

for i in range(1, 11):
    slot = f"account{i}"
    info = load_account_info(slot)
    if not info: continue
    base = f"/opt/telegramforward.old/data/accounts/{slot}"
    gh = read_json(os.path.join(base, "groups_health.json")) or {}
    # parse blocked correctly
    blocked = 0
    total = 0
    if isinstance(gh, dict):
        for k, v in gh.items():
            if k in ("updated_at", "slot", "version"):
                continue
            if isinstance(v, dict):
                total += 1
                if v.get("blocked") or v.get("is_blocked"):
                    blocked += 1
    hist = read_json(os.path.join(base, "group_send_history.json")) or {}
    # inspect structure
    hist_keys = list(hist.keys())[:8] if isinstance(hist, dict) else []
    last_at = hist.get("last_send_at") or hist.get("last_success_at")
    entries = []
    if isinstance(hist.get("entries"), list):
        entries = hist["entries"]
    elif isinstance(hist.get("sends"), list):
        entries = hist["sends"]
    elif isinstance(hist, dict):
        for k,v in hist.items():
            if isinstance(v, dict) and ("status" in v or "sent" in v or "group" in v):
                entries.append(v)
    ok = sum(1 for e in entries[-50:] if isinstance(e, dict) and (
        e.get("status") in ("sent","ok","success") or e.get("ok") is True or e.get("sent") is True
    ))
    fail = sum(1 for e in entries[-50:] if isinstance(e, dict) and (
        e.get("status") in ("failed","error","skip","skipped") or e.get("failed")
    ))
    sd = accounts_sd.get(slot) or {}
    cycle = read_json(os.path.join(base, "cycle_metrics_last.json")) or {}
    pm = read_json(os.path.join(base, "posting_mode.json")) or {}
    print(json.dumps({
        "slot": slot,
        "display": (info.get("display_name") or info.get("name"))[:40],
        "mode_now": pm.get("mode"),
        "joined": info.get("joined_groups"),
        "groups_total": total,
        "groups_blocked": blocked,
        "hist_keys": hist_keys,
        "hist_entries": len(entries),
        "hist_ok_50": ok,
        "hist_fail_50": fail,
        "last_send_at": ts(last_at or sd.get("last_send_at")),
        "shutdown_reason": sd.get("reason"),
        "last_cycle": cycle,
    }, ensure_ascii=False))
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
cmd = f"cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{script}\nPY"
_, stdout, _ = c.exec_command(cmd, timeout=120)
print(stdout.read().decode(errors="replace"))

# sample one group_send_history
_, stdout, _ = c.exec_command("python3 -c \"import json; d=json.load(open('/opt/telegramforward.old/data/accounts/account9/group_send_history.json')); print(type(d), list(d.keys())[:15], str(d)[:500])\" 2>/dev/null", timeout=30)
print("\n=== account9 history sample ===")
print(stdout.read().decode(errors="replace"))

_, stdout, _ = c.exec_command("python3 -c \"import json; d=json.load(open('/opt/telegramforward.old/data/accounts/account1/groups_health.json')); items=[(k,v) for k,v in d.items() if isinstance(v,dict)]; print('items',len(items),'blocked',sum(1 for _,v in items if v.get('blocked'))); print(items[0] if items else 'none')\" 2>/dev/null", timeout=30)
print("\n=== account1 health sample ===")
print(stdout.read().decode(errors="replace"))
c.close()
