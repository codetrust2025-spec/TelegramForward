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
    gh = json.loads((base / "groups_health.json").read_text())
    pm = json.loads((base / "posting_mode.json").read_text()) if (base / "posting_mode.json").exists() else {}
    blocked = json.loads((base / "blocked_groups.json").read_text()) if (base / "blocked_groups.json").exists() else []
    
    print(f"\\n========== {s} ==========")
    print("health_score:", gi.get("health_score"), "execution_policy:", gi.get("execution_policy"))
    print("flood_streak:", gi.get("flood_streak"), "heavy_rate_limit:", gi.get("heavy_rate_limit"))
    print("posting_mode:", pm)
    print("blocked_groups count:", len(blocked) if isinstance(blocked, list) else len(blocked.keys()) if isinstance(blocked, dict) else blocked)
    
    # groups in intelligence with recent outcomes
    groups = gi.get("groups", {})
    skip_reasons = {}
    for g, info in groups.items():
        if isinstance(info, dict):
            r = info.get("last_skip_reason") or info.get("last_result") or info.get("status")
            if r:
                skip_reasons[r] = skip_reasons.get(r, 0) + 1
    print("group intel outcome counts:", dict(sorted(skip_reasons.items(), key=lambda x: -x[1])[:12]))
    
    # cycle skip breakdown from last metrics
    cm = json.loads((base / "cycle_metrics_last.json").read_text())
    print("last cycle:", {k: cm.get(k) for k in ["success","failed","skipped","groups_total","end_reason"]})
    
    # sample groups assigned
    from core.group_assignment import groups_for_slot
    assigned = groups_for_slot(s)
    print("assigned groups:", len(assigned))
    print("first 5 assigned:", assigned[:5])
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()
with sftp.open("/tmp/diag4.py", "w") as f:
    f.write(DIAG)
sftp.close()
_, stdout, stderr = c.exec_command(
    "cd /opt/telegramforward.old && /opt/telegramforward.old/venv/bin/python /tmp/diag4.py 2>&1",
    timeout=90,
)
print(stdout.read().decode("utf-8", errors="replace"))
print(stderr.read().decode("utf-8", errors="replace"))
c.close()
