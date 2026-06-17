"""Deploy offer letter PDF preview (backend + static)."""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST, REMOTE = "187.127.169.159", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def upload_tree(sftp, local_root, remote_root):
    n = 0
    for dirpath, _, filenames in os.walk(local_root):
        for name in filenames:
            local = os.path.join(dirpath, name)
            rel = os.path.relpath(local, local_root).replace("\\", "/")
            remote = f"{remote_root}/{rel}"
            remote_dir = os.path.dirname(remote).replace("\\", "/")
            path = ""
            for p in remote_dir.split("/"):
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
            n += 1
    return n


def main():
    if not PASSWORD:
        print("VPS_PASSWORD required", file=sys.stderr)
        return 1
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PASSWORD, timeout=30)
    sftp = c.open_sftp()
    for rel in ("server.py", "features/data_room_credentials_store.py"):
        sftp.put(os.path.join(REPO, rel), f"{REMOTE}/{rel}")
        print("uploaded", rel)
    n = upload_tree(sftp, os.path.join(REPO, "static"), f"{REMOTE}/static")
    print(f"uploaded {n} static files")
    sftp.close()
    _, o, _ = c.exec_command(
        f"grep -c offer-letters {REMOTE}/server.py; "
        f"mkdir -p {REMOTE}/data/data_room/offer_letters_cache; "
        f"cd {REMOTE} && pm2 restart telegram-backend --update-env 2>&1 | tail -1"
    )
    print(o.read().decode("utf-8", errors="replace"))
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
