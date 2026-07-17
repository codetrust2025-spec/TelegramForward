#!/usr/bin/env python3
"""Revert VPS slot-related files to match current local (post-reset) state."""
from __future__ import annotations
import os, sys
from pathlib import Path
import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
LOCAL_ROOT = Path(__file__).parent.parent

# All files touched by the slot commits — push current (reverted) versions
FILES = [
    "features/slot_screenshot_parse.py",
    "features/ollama_invite_extract.py",
    "core/public_slot_api.py",
    "dashboard/src/pages/SubmitSlotPage.jsx",
    "dashboard/src/index.css",
]

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not PASSWORD:
        raise SystemExit("Set VPS_PASSWORD")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = c.open_sftp()
    for rel in FILES:
        local = LOCAL_ROOT / rel
        if not local.is_file():
            print(f"SKIP (not found locally): {rel}")
            continue
        remote = f"{REMOTE}/{rel}"
        sftp.put(str(local), remote)
        print(f"Reverted {rel}")
    sftp.close()

    # Rebuild static from current local static/ folder
    static_dir = LOCAL_ROOT / "static"
    sftp2 = c.open_sftp()
    for f in (static_dir / "assets").iterdir():
        sftp2.put(str(f), f"/opt/telegramforward.old/static/assets/{f.name}")
        print(f"Static: {f.name}")
    for f in static_dir.iterdir():
        if f.is_file():
            sftp2.put(str(f), f"/opt/telegramforward.old/static/{f.name}")
            print(f"Static: {f.name}")
    sftp2.close()

    cmd = "pm2 restart telegram-backend --update-env && sleep 4 && curl -s -o /dev/null -w 'health %{http_code}' http://127.0.0.1:8000/health"
    _, stdout, stderr = c.exec_command(cmd, timeout=90)
    print(stdout.read().decode("utf-8", errors="replace"))
    c.close()
    print("Done — VPS reverted to current local state.")

if __name__ == "__main__":
    main()
