"""Deploy removal of Arvind senior contact from Karthik AI."""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward.old"
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
    for rel in (
        "core/ai_smart_reply.py",
        "data/ai_smart_reply.json",
        "dashboard/src/config.js",
    ):
        sftp.put(os.path.join(root, rel.replace("/", os.sep)), f"{REMOTE}/{rel}")
        print("uploaded", rel)
    sftp.close()
    _, o, _ = ssh.exec_command(
        f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -8 && "
        "pm2 restart telegram-backend --update-env 2>&1 | tail -3",
        timeout=600,
    )
    print(o.read().decode())
    _, o2, _ = ssh.exec_command(
        f"grep -c Arvind {REMOTE}/core/ai_smart_reply.py || true",
        timeout=30,
    )
    print("Arvind mentions left:", o2.read().decode().strip())
    ssh.close()
    print("Done.")


if __name__ == "__main__":
    main()
