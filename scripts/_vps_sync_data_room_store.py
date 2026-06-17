"""Ensure data room dir exists on VPS and upload local opportunities/handlers config."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> None:
    import paramiko

    if not PASSWORD:
        print("Set VPS_PASSWORD")
        sys.exit(1)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username="root", password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()

    uploads = [
        ("config/dashboard_handlers.yaml", f"{REMOTE}/config/dashboard_handlers.yaml"),
        ("data/data_room/opportunities.json", f"{REMOTE}/data/data_room/opportunities.json"),
    ]
    for rel, remote in uploads:
        local = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(local):
            print("skip missing", rel)
            continue
        remote_dir = os.path.dirname(remote).replace("\\", "/")
        ssh.exec_command(f"mkdir -p {remote_dir}")
        sftp.put(local, remote)
        print("uploaded", rel)

    py = f"{REMOTE}/venv/bin/python"
    _, o, e = ssh.exec_command(
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} -c "
        "\"from features import data_room_store; print('stats', data_room_store.stats_summary())\"",
        timeout=60,
    )
    print(o.read().decode())
    err = e.read().decode()
    if err.strip():
        print(err, file=sys.stderr)

    ssh.exec_command("cd /opt/telegramforward && pm2 restart telegram-backend --update-env")
    sftp.close()
    ssh.close()
    print("Done — reload dashboard_handlers cache on next login.")


if __name__ == "__main__":
    main()
