"""Deploy Data room store + API + dashboard tab to production."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = [
    "features/data_room_store.py",
    "services/data_room_service.py",
    "core/ai_smart_reply.py",
    "dashboard/src/components/DataRoomPanel.jsx",
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
        local = os.path.join(root, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        sftp.put(local, remote)
        print(f"uploaded {rel}")

    sftp.close()

    py = f"{REMOTE}/venv/bin/python"
    cmds = [
        f"cd {REMOTE}/dashboard && npm run build",
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} -m py_compile "
        "features/data_room_store.py services/data_room_service.py server.py",
        f"cd {REMOTE} && PYTHONPATH={REMOTE} pm2 restart telegram-backend --update-env",
        "sleep 5",
        f"curl -s http://127.0.0.1:8000/data-room/stats | head -c 200",
    ]
    for cmd in cmds:
        print(f"\n$ {cmd[:90]}...")
        _, stdout, stderr = ssh.exec_command(cmd, timeout=600)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out.strip():
            print(out)
        if err.strip():
            print(err, file=sys.stderr)

    ssh.close()
    print("\nDone — open Data room tab (hard refresh Ctrl+Shift+R).")


if __name__ == "__main__":
    main()
