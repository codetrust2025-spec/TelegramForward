#!/usr/bin/env python3
"""Deploy candidate stats scoping fix (server.py + dashboard static)."""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import paramiko

from _deploy_common import enforce_git_first, repo_root

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
ROOT = repo_root()
STATIC = ROOT / "static"


def main() -> None:
    if not os.environ.get("SKIP_GIT_GATE"):
        enforce_git_first()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not PWD:
        raise SystemExit("Set VPS_PASSWORD environment variable")

    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    sftp = c.open_sftp()

    sftp.put(str(ROOT / "server.py"), f"{REMOTE}/server.py")
    print("Uploaded server.py")
    sftp.put(str(ROOT / "features" / "candidate_store.py"), f"{REMOTE}/features/candidate_store.py")
    print("Uploaded features/candidate_store.py")
    for rel in (
        "core/dashboard_auth_vps.py",
        "core/dashboard_auth_api.py",
        "core/dashboard_auth.py",
    ):
        local = ROOT / rel
        if local.is_file():
            sftp.put(str(local), f"{REMOTE}/{rel.replace(chr(92), '/')}")
            print(f"Uploaded {rel}")

    n = 0
    for item in STATIC.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(STATIC).as_posix()
        remote = f"{REMOTE}/static/{rel}"
        parent = remote.rsplit("/", 1)[0]
        c.exec_command(f"mkdir -p {parent}")
        sftp.put(str(item), remote)
        n += 1
    sftp.close()
    print(f"Uploaded {n} static files")

    cmd = (
        "pm2 restart telegram-backend --update-env && sleep 4 && "
        "curl -s -o /dev/null -w 'health %{http_code}\\n' http://127.0.0.1:8000/health && "
        f"grep -o 'index-[^\"]*\\.js' {REMOTE}/static/index.html"
    )
    _, stdout, stderr = c.exec_command(cmd, timeout=90)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err.strip():
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    c.close()
    if code != 0:
        raise SystemExit(code)
    print("Done. Hard-refresh https://teleautomation.online (Ctrl+Shift+R)")


if __name__ == "__main__":
    main()
