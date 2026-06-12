#!/usr/bin/env python3
"""Deploy campaign fixes to VPS and remediate account3/account8."""
import json
import os
import socket
import sys
import time
from pathlib import Path

import paramiko

from _deploy_common import enforce_git_first, repo_root

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

enforce_git_first()

PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
LOCAL_TF = repo_root()

UPLOAD = [
    "workers/feature_runtime.py",
    "workers/account_state.py",
    "workers/account_worker.py",
    "features/group_operation.py",
    "core/message_rewrite.py",
    "services/account_manager.py",
]

REMEDIATE = '''
import json
from pathlib import Path

BASE = Path("/opt/telegramforward.old/data/accounts")

for slot in ["account3", "account8"]:
    gi_path = BASE / slot / "group_intelligence.json"
    if not gi_path.exists():
        continue
    gi = json.loads(gi_path.read_text())
    acct = gi.setdefault("account", {})
    acct["health_score"] = max(float(acct.get("health_score") or 100), 95.0)
    acct["delay_multiplier"] = 1.0
    acct["flood_streak"] = 0
    gi_path.write_text(json.dumps(gi, indent=2))

slot = "account8"
blocked_path = BASE / slot / "blocked_groups.json"
gh_path = BASE / slot / "groups_health.json"
if blocked_path.exists() and gh_path.exists():
    blocked = json.loads(blocked_path.read_text())
    if isinstance(blocked, dict):
        blocked_set = set(blocked.keys())
    else:
        blocked_set = set(blocked)
    gh = json.loads(gh_path.read_text())
    detail = gh.get("detail") or {}
    permanent = {g for g, d in detail.items() if isinstance(d, dict) and d.get("bucket") == "blocked"}
    trimmed = blocked_set & permanent
    removed = len(blocked_set) - len(trimmed)
    blocked_path.write_text(json.dumps(sorted(trimmed), indent=2))
    print(f"account8 blocked: {len(blocked_set)} -> {len(trimmed)} (removed {removed} stale)")

print("remediation ok")
'''

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()

print("=== Upload ===")
for rel in UPLOAD:
    local = LOCAL_TF / rel
    remote = f"{REMOTE}/{rel}"
    sftp.put(str(local), remote)
    print(f"  {rel}")

with sftp.open("/tmp/remediate_acct38.py", "w") as f:
    f.write(REMEDIATE)
sftp.close()

print("\n=== Remediate ===")
_, stdout, stderr = c.exec_command(
    f"/opt/telegramforward.old/venv/bin/python /tmp/remediate_acct38.py", timeout=30
)
print(stdout.read().decode() or stderr.read().decode())

print("\n=== PM2 restart ===")
_, stdout, _ = c.exec_command("pm2 restart telegram-backend", timeout=60)
print(stdout.read().decode()[:500])
time.sleep(8)

print("\n=== Start campaign workers ===")
for slot in ["account3", "account8"]:
    _, stdout, _ = c.exec_command(
        f"curl -s -X POST 'http://127.0.0.1:8000/account/{slot}/start?feature=campaign' "
        f"-u admin:$(grep DASHBOARD_PASSWORD {REMOTE}/.env | cut -d= -f2)",
        timeout=20,
    )
    print(f"{slot}:", stdout.read().decode()[:200])

print("\nWaiting 120s for cycle progress...")
time.sleep(120)

VERIFY = '''
import json
from pathlib import Path
for slot in ["account3", "account8"]:
    p = Path(f"/opt/telegramforward.old/data/accounts/{slot}/cycle_metrics_last.json")
    if p.exists():
        cm = json.loads(p.read_text())
        print(slot, "success=", cm.get("success"), "failed=", cm.get("failed"),
              "skipped=", cm.get("skipped"), "groups=", cm.get("groups_processed"))
'''
with c.open_sftp() as sftp:
    with sftp.open("/tmp/verify_acct.py", "w") as f:
        f.write(VERIFY)
_, stdout, _ = c.exec_command("/opt/telegramforward.old/venv/bin/python /tmp/verify_acct.py", timeout=30)
print("\n=== After fix ===")
print(stdout.read().decode())

c.close()
print("Done.")
