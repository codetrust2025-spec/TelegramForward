"""Fix Karthik auto-reply wiring on VPS + wake waiting leads."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = [
    "core/config.py",
    "core/spam_detector.py",
    "services/spam_guard_service.py",
    "core/ai_smart_reply.py",
    "workers/account_worker.py",
    "services/dm_inbox_service.py",
    "services/whatsapp_dispatch.py",
    "server.py",
    "messaging/message_router.py",
    "messaging/task_types.py",
    "messaging/account_queue.py",
    "core/karthik_inbox_sweep.py",
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
        local = os.path.join(root, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        sftp.put(local, remote)
        print(f"uploaded {rel}")

    sftp.close()

    py = f"{REMOTE}/venv/bin/python"
    cmds = [
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} -m py_compile "
        "workers/account_worker.py services/dm_inbox_service.py server.py",
        f"cd {REMOTE} && PYTHONPATH={REMOTE} pm2 restart telegram-backend --update-env",
        "sleep 8",
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} -c \"import asyncio; "
        "from core.ai_smart_reply import catch_up_pending_replies, health; "
        "print('health', health()); "
        "print('catch_up', asyncio.run(catch_up_pending_replies(max_replies=15)))\"",
    ]
    for cmd in cmds:
        print(f"\n$ {cmd[:100]}...")
        _, stdout, stderr = ssh.exec_command(cmd, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out.strip():
            print(out)
        if err.strip():
            print(err, file=sys.stderr)

    ssh.close()
    print("\nDone — hard refresh inbox (Ctrl+Shift+R). Waiting leads should get Karthik replies.")


if __name__ == "__main__":
    main()
