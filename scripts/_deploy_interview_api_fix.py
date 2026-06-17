"""Deploy interview API routes + candidate_store + static build to VPS."""
from __future__ import annotations

import os
import subprocess
import sys

import paramiko

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


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
        print("VPS_PASSWORD required", file=sys.stderr)
        return 1

    print("Building dashboard…")
    subprocess.check_call("npm run build", cwd=os.path.join(REPO, "dashboard"), shell=True)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    for local_rel in ("server.py", "features/candidate_store.py"):
        local = os.path.join(REPO, local_rel)
        remote = f"{REMOTE}/{local_rel.replace(chr(92), '/')}"
        sftp.put(local, remote)
        print(f"uploaded {local_rel}")

    n = upload_tree(sftp, os.path.join(REPO, "static"), f"{REMOTE}/static")
    print(f"uploaded {n} static files")

    _, stdout, _ = client.exec_command(f"cd {REMOTE} && pm2 restart telegram-backend --update-env 2>&1")
    print(stdout.read().decode("utf-8", errors="replace"))

    sftp.close()
    client.close()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
