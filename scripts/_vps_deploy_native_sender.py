"""Deploy native Telegram sender labels + repair inbox."""

from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = (
    "core/dm_store.py",
    "dashboard/src/inbox/MessageBubble.jsx",
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
        f"cd {REMOTE} && ./venv/bin/python -c \""
        "from core.config import ACCOUNTS; "
        "from core.dm_store import repair_outbound_sender_labels; "
        "t=sum(repair_outbound_sender_labels(s) for s in ACCOUNTS); "
        "print('repaired', t)"
        "\"",
        f"cd {REMOTE}/dashboard && npm run build",
        "pm2 restart telegram-backend --update-env 2>/dev/null | tail -3",
    ]
    for c in cmds:
        print(">", c[:72])
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
