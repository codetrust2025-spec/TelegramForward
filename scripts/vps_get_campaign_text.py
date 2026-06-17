#!/usr/bin/env python3
import socket, paramiko, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

script = r'''
import json
from pathlib import Path
from core.fleet_defaults import get_fleet_defaults
text = get_fleet_defaults().get("campaign_message") or ""
print("MESSAGE_LEN", len(text))
print("---MESSAGE---")
print(text)
print("---END---")

# check which accounts might admin jobsupport0
from core.account_info_store import load_account_info
for i in range(1, 11):
    slot = f"account{i}"
    info = load_account_info(slot)
    if info and info.get("phone"):
        print(slot, info.get("display_name") or info.get("name"), info.get("username") or "")
'''
_, stdout, _ = c.exec_command(
    f"cd /opt/telegramforward.old && set -a && . ./.env && set +a && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{script}\nPY",
    timeout=60,
)
print(stdout.read().decode("utf-8", errors="replace"))
c.close()
