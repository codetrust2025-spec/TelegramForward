"""Deploy event-loop fix for Reconnecting to server (stats blocking WS)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = [
    "server.py",
    "services/account_manager.py",
    "services/dm_inbox_service.py",
]

REMOTE_CMDS = [
    "pm2 restart telegram-backend",
    "sleep 5 && curl -sf -m 8 http://127.0.0.1:8000/health && echo HEALTH_OK",
]


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()
    for rel in FILES:
        local = os.path.join(repo, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        print(f"upload {rel}")
        sftp.put(local, remote)
    sftp.close()

    for cmd in REMOTE_CMDS:
        print(f"\n>>> {cmd}")
        _stdin, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=120)
        out = stdout.read().decode("utf-8", errors="replace")
        if out:
            print(out[-4000:])
        if stdout.channel.recv_exit_status() != 0:
            client.close()
            return 1

    client.close()
    print("\nReconnect fix deployed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
