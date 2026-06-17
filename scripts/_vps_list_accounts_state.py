"""List logged-in slots, posting mode, shutdown on VPS."""
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
cmd = r"""
PYTHONPATH=/opt/telegramforward /opt/telegramforward/venv/bin/python <<'PY'
from core.config import ACCOUNT_SLOTS
from core.account_info_store import load_account_info
from core.posting_mode import load_posting_mode
from core.account_shutdown import is_shutdown_active, get_shutdown_info

for slot in ACCOUNT_SLOTS[:15]:
    info = load_account_info(slot)
    if not info or not (info.get("phone") or info.get("user_id")):
        continue
    pm = load_posting_mode(slot)
    name = info.get("name") or info.get("display_name") or "?"
    shut = is_shutdown_active(slot)
    print(
        f"{slot}: {name[:28]:28} | camp={pm.campaign_enabled} fwd={pm.forwarding_enabled} "
        f"| shutdown={shut}"
    )
PY
"""
_, o, _ = c.exec_command(cmd, timeout=30)
print(o.read().decode())
c.close()
