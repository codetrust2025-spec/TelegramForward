"""Deploy inbox sender badges (AI vs operator name)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = [
    "core/dm_store.py",
    "services/dm_inbox_service.py",
    "messaging/message_router.py",
    "workers/account_worker.py",
    "core/ai_smart_reply.py",
    "server.py",
    "dashboard/src/inbox/MessageBubble.jsx",
    "dashboard/src/components/InboxPanel.jsx",
    "dashboard/src/index.css",
]


def main() -> None:
    import paramiko

    if not PASSWORD:
        print("Set VPS_PASSWORD")
        sys.exit(1)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()
    for rel in FILES:
        sftp.put(os.path.join(root, rel.replace("/", os.sep)), f"{REMOTE}/{rel}")
        print(f"uploaded {rel}")
    sftp.close()
    py = f"{REMOTE}/venv/bin/python"
    for cmd in [
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} -m py_compile core/dm_store.py server.py",
        f"cd {REMOTE}/dashboard && npm run build",
        f"cd {REMOTE} && pm2 restart telegram-backend --update-env",
    ]:
        _, o, e = ssh.exec_command(cmd, timeout=300)
        print(o.read().decode("utf-8", errors="replace")[:500])
    ssh.close()
    print("Done — hard refresh inbox; new replies show AI or your username.")


if __name__ == "__main__":
    main()
