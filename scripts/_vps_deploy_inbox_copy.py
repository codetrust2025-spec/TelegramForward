"""Deploy inbox message copy (hover + right-click)."""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = (
    "dashboard/src/inbox/MessageBubble.jsx",
    "dashboard/src/inbox/inboxLayout.css",
    "dashboard/src/utils/copyToClipboard.js",
)


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
    for rel in FILES:
        sftp.put(os.path.join(root, rel.replace("/", os.sep)), f"{REMOTE}/{rel}")
        print("uploaded", rel)
    sftp.close()
    _, o, e = ssh.exec_command(
        f"cd {REMOTE}/dashboard && npm run build && cd {REMOTE} && "
        "bash scripts/production_update.sh 2>/dev/null | tail -8",
        timeout=600,
    )
    print(o.read().decode())
    err = e.read().decode()
    if err.strip():
        print(err, file=sys.stderr)
    ssh.close()
    print("Done — hard refresh inbox (Denver thread).")


if __name__ == "__main__":
    main()
