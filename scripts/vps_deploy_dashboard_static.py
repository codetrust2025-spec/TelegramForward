#!/usr/bin/env python3
"""Deploy dashboard static bundle only."""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
ROOT = Path(__file__).resolve().parent.parent / "static"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    sftp = c.open_sftp()
    n = 0
    for item in ROOT.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(ROOT).as_posix()
        remote = f"{REMOTE}/static/{rel}"
        parent = remote.rsplit("/", 1)[0]
        c.exec_command(f"mkdir -p {parent}")
        sftp.put(str(item), remote)
        n += 1
    sftp.close()
    _, stdout, _ = c.exec_command(
        f"grep -o 'index-[^\"]*\\.js' {REMOTE}/static/index.html; "
        "curl -s -o /dev/null -w 'health %{http_code}\\n' http://127.0.0.1:8000/health",
        timeout=30,
    )
    print(stdout.read().decode())
    print(f"Uploaded {n} static files")
    c.close()
    print("Done. Hard-refresh https://teleautomation.online (Ctrl+Shift+R)")


if __name__ == "__main__":
    main()
