#!/usr/bin/env python3
"""Fetch VPS worker/core files and sync to TelegramForward repo."""
import os
import socket
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
LOCAL = Path(r"C:\Users\codet\TelegramForward")

FILES = [
    "workers/feature_runtime.py",
    "workers/account_state.py",
    "workers/account_worker.py",
    "core/account_features.py",
    "core/message_rewrite.py",
    "core/telegram_forward.py",
    "core/group_assignment.py",
    "services/account_registry.py",
    "services/account_manager.py",
]

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()

print("=== Sync VPS -> TelegramForward ===")
for rel in FILES:
    remote = f"{REMOTE}/{rel}"
    local = LOCAL / rel
    local.parent.mkdir(parents=True, exist_ok=True)
    try:
        sftp.get(remote, str(local))
        print(f"OK  {rel} ({local.stat().st_size} bytes)")
    except Exception as e:
        print(f"SKIP {rel}: {e}")

sftp.close()
c.close()
print("\nDone.")
