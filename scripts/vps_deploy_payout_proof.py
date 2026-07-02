#!/usr/bin/env python3
"""Deploy handler payout proof feature: backend + static dashboard."""
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

# Files that changed for this feature
FILES = [
    "server.py",
    "features/handler_expenses.py",
    "scripts/_vps_candidatesModule.jsx",
]

STATIC_FILES = []  # We'll upload the whole static/ dir


def upload_directory(sftp, local_dir: Path, remote_dir: str):
    """Recursively upload directory contents."""
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        sftp.mkdir(remote_dir)

    for item in local_dir.iterdir():
        remote_path = f"{remote_dir}/{item.name}"
        if item.is_dir():
            upload_directory(sftp, item, remote_path)
        else:
            sftp.put(str(item), remote_path)
            print(f"  ↑ {item.relative_to(LOCAL_ROOT)}")


def main() -> None:
    enforce_git_first()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not PASSWORD:
        raise SystemExit("Set VPS_PASSWORD environment variable")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"🔌 Connecting to {HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    # Upload backend files
    print("\n📤 Uploading backend files...")
    for rel in FILES:
        local = LOCAL_ROOT / rel
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        if not local.is_file():
            print(f"  ⚠ Skipping (not found): {rel}")
            continue
        # Ensure remote directory exists
        remote_dir = "/".join(remote.split("/")[:-1])
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            sftp.mkdir(remote_dir)
        sftp.put(str(local), remote)
        print(f"  ✓ {rel}")

    # Upload static assets
    print("\n📤 Uploading dashboard static files...")
    local_static = LOCAL_ROOT / "static"
    remote_static = f"{REMOTE}/static"
    if local_static.exists():
        upload_directory(sftp, local_static, remote_static)
    else:
        print("  ⚠ static/ directory not found")

    sftp.close()

    # Restart backend
    print("\n🔄 Restarting backend...")
    cmd = "pm2 restart telegram-backend --update-env && sleep 4 && curl -s http://127.0.0.1:8000/health"
    _, stdout, stderr = client.exec_command(cmd, timeout=90)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    code = stdout.channel.recv_exit_status()
    client.close()

    if code != 0:
        print(f"\n⚠ Backend restart returned exit code {code}")
    else:
        print("\n✅ Deploy complete! Handler payout proof feature is live.")
    print("\n📝 Test: Open handler payouts modal → screenshot upload should be required.")


if __name__ == "__main__":
    main()
