#!/usr/bin/env python3
"""Deploy hourly IST label fix in send_stats.py."""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import paramiko

from _deploy_common import enforce_git_first, repo_root

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
LOCAL = repo_root() / "core" / "send_stats.py"


def main() -> None:
    enforce_git_first()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    sftp = c.open_sftp()
    sftp.put(str(LOCAL), f"{REMOTE}/core/send_stats.py")
    sftp.close()
    _, stdout, _ = c.exec_command(
        f"cd {REMOTE} && source venv/bin/activate && python3 - <<'PY'\n"
        "from core.send_stats import hourly_bucket_labels\n"
        "labels = hourly_bucket_labels(24)\n"
        "shown = [(i, labels[i]) for i in range(24) if labels[i]]\n"
        "print('IST labels:', shown)\n"
        "PY",
        timeout=30,
    )
    print(stdout.read().decode())
    c.exec_command("pm2 restart telegram-backend")
    c.close()
    print("Done")


if __name__ == "__main__":
    main()
