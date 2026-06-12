#!/usr/bin/env python3
import os, socket, paramiko, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

script = r'''
import json
from core.config import ACCOUNT_SLOTS
from core.account_info_store import load_account_info
from core.posting_mode import load_posting_mode

# shutdown
try:
    with open("/opt/telegramforward.old/data/account_shutdown.json") as f:
        sd = json.load(f)
except Exception:
    sd = {}

for slot in [f"account{i}" for i in range(1, 11)]:
    info = load_account_info(slot)
    if not info: continue
    pm = load_posting_mode(slot)
    shut = sd.get(slot) or sd.get("accounts", {}).get(slot)
    print(json.dumps({
        "slot": slot,
        "display": info.get("display_name"),
        "mode": pm.mode,
        "campaign": pm.campaign_enabled,
        "forwarding": pm.forwarding_enabled,
        "shutdown": shut,
    }, ensure_ascii=False, default=str))
'''
_, stdout, _ = c.exec_command(f"cd /opt/telegramforward.old && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{script}\nPY", timeout=60)
print(stdout.read().decode())

for cmd in [
    "grep -rn 'start_account\\|def start' /opt/telegramforward.old/server.py /opt/telegramforward.old/core/*.py 2>/dev/null | head -30",
    "cat /opt/telegramforward.old/data/account_shutdown.json 2>/dev/null | head -80",
]:
    print("\n===", cmd[:70])
    _, stdout, _ = c.exec_command(cmd, timeout=30)
    print(stdout.read().decode(errors="replace")[:5000])
c.close()
