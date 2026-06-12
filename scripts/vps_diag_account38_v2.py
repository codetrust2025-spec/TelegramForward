#!/usr/bin/env python3
import json, os, socket, sys
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
BASE = "/opt/telegramforward.old/data/accounts"

DIAG = f'''
import json
from pathlib import Path
BASE = Path("{BASE}")
slots = ["account3", "account8", "account5", "account7", "account10"]
out = {{}}
for s in slots:
    d = {{"slot": s}}
    acct = BASE / s
    for name in ["cycle_metrics_last.json", "groups_health.json", "group_send_history.json"]:
        p = acct / name
        if p.exists():
            raw = json.loads(p.read_text())
            if name == "groups_health.json":
                b = raw.get("buckets", raw) if isinstance(raw, dict) else {{}}
                d["groups"] = {{
                    "healthy": len(b.get("healthy") or []),
                    "blocked": len(b.get("blocked") or []),
                    "skipped": len(b.get("skipped") or []),
                }}
            elif name == "group_send_history.json":
                entries = raw if isinstance(raw, list) else raw.get("entries", [])
                d["sends"] = len(entries)
                d["last_send"] = entries[-1] if entries else None
            else:
                d["cycle"] = raw
        else:
            d[name] = "missing"
    msg = acct / "message.txt"
    d["has_message"] = msg.exists()
    if msg.exists():
        d["message_preview"] = msg.read_text(encoding="utf-8", errors="replace")[:100]
    out[s] = d
print(json.dumps(out, indent=2))

# fleet defaults + running workers
for p in [
    "/opt/telegramforward.old/data/fleet_defaults.json",
    "/opt/telegramforward.old/data/.running_workers.json",
]:
    print("\\n===", p, "===")
    print(Path(p).read_text()[:800])
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/diag3.py", "w") as f:
    f.write(DIAG)
sftp.close()
_, stdout, _ = c.exec_command("/opt/telegramforward.old/venv/bin/python /tmp/diag3.py", timeout=60)
print(stdout.read().decode("utf-8", errors="replace"))

# Check account features config
_, stdout, _ = c.exec_command(
    "grep -r 'account3\\|account8' /opt/telegramforward.old/data/accounts/account3/*.json /opt/telegramforward.old/data/accounts/account8/*.json 2>/dev/null | head -5; "
    "ls /opt/telegramforward.old/data/accounts/account3/; "
    "ls /opt/telegramforward.old/data/accounts/account8/",
    timeout=30,
)
print("\n=== FILES ===")
print(stdout.read().decode())

# Find group intelligence
_, stdout, _ = c.exec_command(
    "find /opt/telegramforward.old -name 'group_intelligence.json' 2>/dev/null; "
    "find /opt/telegramforward.old/data/accounts -name '*intel*' 2>/dev/null | head -10",
    timeout=30,
)
print("\n=== INTEL FILES ===")
print(stdout.read().decode())

c.close()
