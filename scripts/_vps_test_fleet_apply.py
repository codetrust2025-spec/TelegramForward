import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
cmd = r"""
PYTHONPATH=/opt/telegramforward /opt/telegramforward/venv/bin/python <<'PY'
from services.fleet_setup_service import apply_forwarding_bulk
from services.account_manager import AccountManager
from core.posting_mode import load_posting_mode

m = AccountManager()
r = apply_forwarding_bulk(
    registry=m,
    source_url="https://t.me/jobsupport0/161879",
)
print("updated", len(r["updated"]), r["updated"])
print("skipped_running", r.get("skipped_running"))
print("skipped_mode", r.get("skipped_mode"))
print("errors", r.get("errors"))
for s in ["account2","account5"]:
    pm = load_posting_mode(s)
    print(s, "fwd", pm.forwarding_enabled, "camp", pm.campaign_enabled)
PY
"""
_, o, e = c.exec_command(cmd, timeout=60)
print(o.read().decode())
err = e.read().decode().strip()
if err:
    print("stderr", err)
c.close()
