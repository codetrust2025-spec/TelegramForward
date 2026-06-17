"""Enable forwarding mode for account11 if logged in (one-off after visibility fix)."""
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
cmd = """
PYTHONPATH=/opt/telegramforward /opt/telegramforward/venv/bin/python <<'PY'
from core.posting_mode import load_posting_mode, set_posting_mode
from core.account_info_store import load_account_info

slot = "account11"
info = load_account_info(slot)
if not (info and (info.get("phone") or info.get("user_id"))):
    print("account11 not logged in")
else:
    pm = load_posting_mode(slot)
    print("before", pm.to_dict(slot))
    set_posting_mode(slot, "forwarding", forward_dispatch="auto",
                     campaign_enabled=False, forwarding_enabled=True)
    print("after", load_posting_mode(slot).to_dict(slot))
PY
"""
_, o, _ = c.exec_command(cmd, timeout=30)
print(o.read().decode())
c.close()
