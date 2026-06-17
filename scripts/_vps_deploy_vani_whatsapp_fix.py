"""Deploy Vani contact fix (WhatsApp +91 90323 88581 / wa.me/919032388581)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = (
    ("core/ai_smart_reply.py", f"{REMOTE}/core/ai_smart_reply.py"),
    ("core/karthik_economy_preset.py", f"{REMOTE}/core/karthik_economy_preset.py"),
)


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()
    for rel, remote in FILES:
        local = os.path.join(repo, rel.replace("/", os.sep))
        print(f"  upload {rel}")
        sftp.put(local, remote)
    sftp.close()

    _, o, _ = client.exec_command("pm2 restart telegram-backend", timeout=45)
    print("pm2:", o.read().decode().strip()[-300:])
    client.close()
    print("Vani contact deployed — +91 90323 88581 / wa.me/919032388581")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
