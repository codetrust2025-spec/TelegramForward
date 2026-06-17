"""Deploy inbox media fixes to live PM2 root (telegramforward.old)."""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = (
    "core/dm_media.py",
    "core/dm_store.py",
    "services/dm_inbox_service.py",
    "dashboard/src/inbox/inboxUiUtils.js",
    "dashboard/src/inbox/MessageBubble.jsx",
    "dashboard/src/inbox/InboxMediaAttachment.jsx",
    "dashboard/src/inbox/inboxLayout.css",
    "dashboard/src/index.css",
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
    cmds = [
        "rm -f /opt/telegramforward.old/data/accounts/account7/dm_media_cache/7282523499_6299* "
        "/opt/telegramforward.old/data/accounts/account7/dm_media_cache/8345253416_6335*",
        f"cd {REMOTE}/dashboard && npm run build",
        f"cd {REMOTE} && bash scripts/production_update.sh 2>/dev/null | tail -6",
        "pm2 restart telegram-backend --update-env 2>/dev/null | tail -3",
        f"cd {REMOTE} && ./venv/bin/python scripts/_sticker_debug_remote.py",
    ]
    for c in cmds:
        print(">", c[:70])
        _, o, e = ssh.exec_command(c, timeout=600)
        out = o.read().decode()
        if out.strip():
            print(out)
        err = e.read().decode()
        if err.strip():
            print(err, file=sys.stderr)
    ssh.close()
    print("Done — hard refresh inbox.")


if __name__ == "__main__":
    main()
