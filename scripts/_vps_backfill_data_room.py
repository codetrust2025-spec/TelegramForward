"""Backfill data room from CRM/inbox (e.g. Arun Kumar N support provider)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
# Empty = scan all CRM leads; set e.g. BACKFILL_NAME=arun to filter by name
NAME = os.environ.get("BACKFILL_NAME", "")


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

    for rel in ("services/data_room_service.py",):
        local = os.path.join(root, rel.replace("/", os.sep))
        sftp.put(local, f"{REMOTE}/{rel}")
        print(f"uploaded {rel}")
    sftp.close()

    py = f"{REMOTE}/venv/bin/python"
    cmd = (
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} -c \""
        "from services.data_room_service import backfill_from_crm; "
        f"rows = backfill_from_crm(name_contains={NAME!r}); "
        "print('saved', len(rows)); "
        "[print(r.get('id'), r.get('name'), r.get('opportunity_type'), r.get('tech_stack')) for r in rows]"
        "\""
    )
    print(cmd[:120], "...")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err, file=sys.stderr)
    ssh.close()


if __name__ == "__main__":
    main()
