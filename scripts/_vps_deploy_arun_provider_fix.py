"""Deploy support-provider / on-job routing fixes for partner threads."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = [
    "core/ai_smart_reply.py",
    "services/data_room_service.py",
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
        sftp.put(local, f"{REMOTE}/{rel}")
        print(f"uploaded {rel}")
    sftp.close()

    py = f"{REMOTE}/venv/bin/python"
    cmds = [
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} -m py_compile "
        "core/ai_smart_reply.py services/data_room_service.py",
        f"cd {REMOTE} && PYTHONPATH={REMOTE} pm2 restart telegram-backend --update-env",
        "sleep 6",
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} -c \""
        "from services.data_room_service import backfill_from_crm; "
        "rows = backfill_from_crm(name_contains='arun'); "
        "print('saved', len(rows)); "
        "[print(r.get('id'), r.get('name'), r.get('volume_hint'), (r.get('summary') or '')[:80]) for r in rows]"
        "\"",
    ]
    for cmd in cmds:
        print(f"\n$ {cmd[:95]}...")
        _, stdout, stderr = ssh.exec_command(cmd, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out.strip():
            print(out)
        if err.strip():
            print(err, file=sys.stderr)

    ssh.close()
    print("\nDone — hard refresh dashboard; Arun thread uses on-job provider replies now.")


if __name__ == "__main__":
    main()
