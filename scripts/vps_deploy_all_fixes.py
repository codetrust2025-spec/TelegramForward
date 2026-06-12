#!/usr/bin/env python3
"""Deploy worker fixes (feature_runtime) + dashboard static to VPS."""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
ROOT = Path(__file__).resolve().parent.parent
TF = Path(r"C:\Users\codet\TelegramForward")

WORKER_FILES = [
    "workers/feature_runtime.py",
    "workers/account_state.py",
    "workers/account_worker.py",
]

CORE_FILES = [
    "core/send_stats.py",
    "core/daily_stats.py",
    "core/groups_store.py",
    "core/group_send_stats.py",
]


def connect() -> paramiko.SSHClient:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, sock=sock)
    return c


def ensure_remote_dir(c: paramiko.SSHClient, remote_dir: str) -> None:
    c.exec_command(f"mkdir -p {remote_dir}")


def put_file(c: paramiko.SSHClient, sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    ensure_remote_dir(c, remote.rsplit("/", 1)[0])
    try:
        sftp.put(str(local), remote)
    except OSError as exc:
        print(f"SKIP unreadable {local}: {exc}")


def main() -> None:
    c = connect()
    sftp = c.open_sftp()

    print("\n=== Core modules (TelegramForward) ===")
    for rel in CORE_FILES:
        local = TF / rel
        remote = f"{REMOTE}/{rel}"
        if not local.exists():
            print(f"SKIP missing {local}")
            continue
        put_file(c, sftp, local, remote)
        print(f"  {rel}")

    print("\n=== Worker files (TelegramForward) ===")
    for rel in WORKER_FILES:
        local = TF / rel
        remote = f"{REMOTE}/{rel}"
        if not local.exists():
            print(f"SKIP missing {local}")
            continue
        put_file(c, sftp, local, remote)
        print(f"  {rel}")

    print("\n=== Dashboard source (full src tree) ===")
    src_root = ROOT / "dashboard" / "src"
    count = 0
    for item in src_root.rglob("*"):
        if item.is_file():
            rel = item.relative_to(ROOT).as_posix()
            remote = f"{REMOTE}/{rel}"
            put_file(c, sftp, item, remote)
            count += 1
    print(f"  uploaded {count} source files")

    static = ROOT / "static"
    if (static / "index.html").exists():
        print("\n=== Static bundle ===")
        n = 0
        for item in static.rglob("*"):
            if item.is_file():
                rel = item.relative_to(static).as_posix()
                put_file(c, sftp, item, f"{REMOTE}/static/{rel}")
                n += 1
        print(f"  uploaded {n} files")

    sftp.close()
    _, stdout, _ = c.exec_command("pm2 restart telegram-backend", timeout=60)
    print(stdout.read().decode())
    c.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
