"""Restore Data room page on production."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_LOCAL = os.path.join(REPO, "static")

UPLOAD_FILES = [
    "server.py",
    "features/data_room_credentials_store.py",
    "dashboard/src/components/DataRoomPanel.jsx",
    "dashboard/src/components/DataRoomVaultSection.jsx",
    "dashboard/src/index.css",
    "data/data_room/credentials.json",
]


def upload_tree(sftp: paramiko.SFTPClient, local_root: str, remote_root: str) -> int:
    count = 0
    for dirpath, _dirnames, filenames in os.walk(local_root):
        for name in filenames:
            local = os.path.join(dirpath, name)
            rel = os.path.relpath(local, local_root).replace("\\", "/")
            remote = f"{remote_root}/{rel}"
            remote_dir = os.path.dirname(remote).replace("\\", "/")
            parts = remote_dir.split("/")
            path = ""
            for p in parts:
                if not p:
                    continue
                path += f"/{p}"
                try:
                    sftp.stat(path)
                except OSError:
                    try:
                        sftp.mkdir(path)
                    except OSError:
                        pass
            sftp.put(local, remote)
            count += 1
    return count


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()
    for rel in UPLOAD_FILES:
        local = os.path.join(REPO, rel)
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        os.makedirs(os.path.dirname(local), exist_ok=True)
        remote_dir = os.path.dirname(remote).replace("\\", "/")
        client.exec_command(f"mkdir -p {remote_dir}")
        sftp.put(local, remote)
        print("uploaded", rel)
    n = upload_tree(sftp, STATIC_LOCAL, f"{REMOTE}/static")
    print(f"uploaded {n} static files")
    sftp.close()
    for cmd in [
        f"cd {REMOTE} && pm2 restart telegram-backend",
        f"grep -c 'Data room' {REMOTE}/static/assets/app-*.js | tail -1",
        f"grep -c 'Offer letters for proof' {REMOTE}/static/assets/app-*.js | tail -1",
    ]:
        print(">>>", cmd)
        _, o, _ = client.exec_command(cmd, timeout=120)
        print(o.read().decode("utf-8", "replace")[:500])
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
