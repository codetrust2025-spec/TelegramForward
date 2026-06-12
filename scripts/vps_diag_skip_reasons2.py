#!/usr/bin/env python3
import json, os, socket, sys
import paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")

DIAG = '''
import json
from pathlib import Path

for s in ["account3", "account8", "account10"]:
    base = Path(f"/opt/telegramforward.old/data/accounts/{s}")
    gi = json.loads((base / "group_intelligence.json").read_text())
    pm = json.loads((base / "posting_mode.json").read_text()) if (base / "posting_mode.json").exists() else {}
    blocked = json.loads((base / "blocked_groups.json").read_text()) if (base / "blocked_groups.json").exists() else []
    
    print(f"\\n========== {s} ==========")
    acct = gi.get("account", gi)
    for k in ["health_score", "execution_policy", "flood_streak", "heavy_rate_limit", "delay_multiplier"]:
        print(f"  {k}:", acct.get(k) if isinstance(acct, dict) else gi.get(k))
    print("  posting_mode mode:", pm.get("mode"), "campaign:", pm.get("campaign_enabled"))
    
    blen = len(blocked) if isinstance(blocked, list) else len(blocked) if isinstance(blocked, dict) else 0
    print("  blocked_groups:", blen)
    
    groups = gi.get("groups", {})
    skip_reasons = {}
    still_latest = 0
    for g, info in groups.items():
        if not isinstance(info, dict):
            continue
        r = info.get("last_skip_reason") or info.get("last_result") or info.get("status")
        if r:
            skip_reasons[r] = skip_reasons.get(r, 0) + 1
        if info.get("still_latest") or info.get("message_is_latest"):
            still_latest += 1
    print("  intel outcomes:", dict(sorted(skip_reasons.items(), key=lambda x: -x[1])[:8]))
    print("  still_latest flags:", still_latest)
    
    cm = json.loads((base / "cycle_metrics_last.json").read_text())
    print("  last cycle:", {k: cm.get(k) for k in ["success","failed","skipped","groups_total"]})
    
    sh = base / "send_history.json"
    if sh.exists():
        hist = json.loads(sh.read_text())
        recent = hist[-3:] if isinstance(hist, list) else list(hist.values())[-3:]
        print("  send_history tail:", recent)
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/diag5.py", "w") as f:
    f.write(DIAG)
sftp.close()
_, stdout, _ = c.exec_command("/opt/telegramforward.old/venv/bin/python /tmp/diag5.py", timeout=60)
print(stdout.read().decode("utf-8", errors="replace"))

# List worker-related files diff
_, stdout, _ = c.exec_command(
    "ls /opt/telegramforward.old/workers/; "
    "ls /opt/telegramforward.old/core/ | grep -E 'group|message|partition|output|feature|campaign|forward'",
    timeout=20,
)
print("\n=== VPS workers + core ===")
print(stdout.read().decode())
c.close()
