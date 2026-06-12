#!/usr/bin/env python3
"""Deploy dashboard auth routes fix to VPS and restart backend."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

from _deploy_common import enforce_git_first, repo_root

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
LOCAL_ROOT = repo_root()

FILES = [
    "server.py",
    "services/account_manager.py",
    "core/dashboard_auth.py",
    "core/dashboard_auth_api.py",
    "core/dashboard_access.py",
    "core/dashboard_auth_vps.py",
]


def main() -> None:
    enforce_git_first()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not PASSWORD:
        raise SystemExit("Set VPS_PASSWORD environment variable")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    for rel in FILES:
        local = LOCAL_ROOT / rel
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        if not local.is_file():
            raise SystemExit(f"Missing local file: {local}")
        sftp.put(str(local), remote)
        print(f"Uploaded {rel}")

    sftp.close()

    checks = [
        "pm2 restart telegram-backend --update-env",
        "sleep 4",
        "curl -s http://127.0.0.1:8000/auth/status",
        "curl -s -X POST http://127.0.0.1:8000/auth/logout",
    ]
    cmd = " && ".join(checks)
    _, stdout, stderr = client.exec_command(cmd, timeout=90)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    client.close()
    if code != 0:
        raise SystemExit(code)
    print("Done.")


if __name__ == "__main__":
    main()
