"""Deploy Karthik 429 rule-based fallback to VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local = os.path.join(repo, "core", "ai_smart_reply.py")
    remote = f"{REMOTE}/core/ai_smart_reply.py"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()
    print(f"  upload core/ai_smart_reply.py")
    sftp.put(local, remote)
    sftp.close()

    _, o, _ = client.exec_command("pm2 restart telegram-backend", timeout=45)
    print("pm2:", o.read().decode().strip()[-300:])
    client.close()
    print("Karthik fallback deployed — clients get rule-based replies during OpenAI 429")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
