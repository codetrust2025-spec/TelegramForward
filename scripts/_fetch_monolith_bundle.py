"""Download monolith bundle from VPS for daily ops extraction."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE_JS = f"{REMOTE}/static/assets/dashboard.bundle.js"
LOCAL_DIR = os.path.join(REPO, "static", "assets")
LOCAL_JS = os.path.join(LOCAL_DIR, "dashboard.bundle.js")


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD required", file=sys.stderr)
        return 1
    os.makedirs(LOCAL_DIR, exist_ok=True)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()
    sftp.get(REMOTE_JS, LOCAL_JS)
    sftp.close()
    client.close()
    print(f"Downloaded {LOCAL_JS} ({os.path.getsize(LOCAL_JS)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
