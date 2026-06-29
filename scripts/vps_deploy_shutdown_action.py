#!/usr/bin/env python3
"""Deploy the manual move-to-shutdown-list endpoint (server.py) and restart backend."""
from __future__ import annotations

import os
import sys

import paramiko

from _deploy_common import enforce_git_first, repo_root

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
LOCAL_ROOT = repo_root()

FILES = [
    "server.py",
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
        "curl -s -o /dev/null -w 'health %{http_code}\\n' http://127.0.0.1:8000/health",
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
