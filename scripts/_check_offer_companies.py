"""Print offer letter company names from production."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmd = (
    f"cd {REMOTE} && venv/bin/python -c "
    "\"from features.data_room_credentials_store import get_credentials; "
    "rows=get_credentials().get('offer_letters',[]); "
    "[print(r.get('id'), '|', r.get('company_name') or '-', '|', r.get('source') or '-', '|', r.get('handler') or '-', '|', (r.get('notes') or '-')[:40]) for r in rows]\""
)
_, o, e = c.exec_command(cmd, timeout=60)
print(o.read().decode("utf-8", "replace"))
err = e.read().decode("utf-8", "replace")
if err:
    print("ERR:", err)
c.close()
