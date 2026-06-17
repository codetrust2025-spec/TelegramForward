"""Diagnose Karthik AI auto-reply on VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
LOCAL_SCRIPT = os.path.join(os.path.dirname(__file__), "_diag_karthik_remote.py")


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()
    remote_script = f"{REMOTE}/scripts/_diag_karthik_remote.py"
    sftp.put(LOCAL_SCRIPT, remote_script)

    stdin, stdout, stderr = client.exec_command(
        f"cd {REMOTE} && ./venv/bin/python scripts/_diag_karthik_remote.py",
        timeout=120,
    )
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out)
    if err.strip():
        print("STDERR:", err, file=sys.stderr)

    stdin, stdout, stderr = client.exec_command(
        "pm2 logs telegram-backend --lines 80 --nostream 2>&1 | tail -40",
        timeout=60,
    )
    print("\n>>> recent backend logs")
    print(stdout.read().decode("utf-8", errors="replace"))

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
