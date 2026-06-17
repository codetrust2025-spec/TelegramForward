"""Deploy per-chat export feature."""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = (
    "features/inbox_export.py",
    "server.py",
    "dashboard/src/utils/exportInboxChat.js",
    "dashboard/src/inbox/ChatHeader.jsx",
    "dashboard/src/components/crm/ChatWindow.jsx",
    "dashboard/src/components/InboxPanel.jsx",
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
    _, o, _ = ssh.exec_command(
        f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -6 && "
        "pm2 restart telegram-backend --update-env 2>&1 | tail -3",
        timeout=600,
    )
    print(o.read().decode())
    ssh.close()
    print("Done — hard refresh, open chat ⋮ menu → Export chat.")


if __name__ == "__main__":
    main()
