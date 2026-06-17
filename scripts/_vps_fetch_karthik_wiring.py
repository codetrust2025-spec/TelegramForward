"""Fetch Karthik wiring files from VPS."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(r"C:\Users\codet\TelegramForward")
REMOTE = "/opt/telegramforward"

FILES = [
    "core/karthik_inbox_sweep.py",
    "messaging/message_router.py",
    "messaging/task_types.py",
    "messaging/account_queue.py",
    "workers/account_worker.py",
    "services/dm_inbox_service.py",
    "server.py",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
sftp = c.open_sftp()
for rel in FILES:
    local = ROOT / rel
    local.parent.mkdir(parents=True, exist_ok=True)
    try:
        sftp.get(f"{REMOTE}/{rel}", str(local))
        print("saved", rel)
    except OSError as e:
        print("skip", rel, e)
sftp.close()
c.close()
