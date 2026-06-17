"""Upload and run Karthik remote check on VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> int:
    import paramiko

    if not PASSWORD:
        print("VPS_PASSWORD not set")
        return 1

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local = os.path.join(repo, "scripts", "_vps_karthik_remote_check.py")

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = c.open_sftp()
    sftp.put(local, f"{REMOTE}/scripts/_vps_karthik_remote_check.py")
    sftp.close()

    _, o, e = c.exec_command(
        f"cd {REMOTE} && PYTHONPATH={REMOTE} python3 scripts/_vps_karthik_remote_check.py",
        timeout=120,
    )
    print(o.read().decode())
    err = e.read().decode().strip()
    if err:
        print("STDERR:", err)

    _, o2, _ = c.exec_command(
        "pm2 logs telegram-backend --nostream --lines 500 2>/dev/null "
        "| grep 429 | tail -15",
        timeout=60,
    )
    print("--- 429 errors (recent) ---")
    print(o2.read().decode())

    _, o3, _ = c.exec_command(
        "grep -E '^(AI_|OPENAI_)' /opt/telegramforward.old/.env 2>/dev/null "
        "| sed 's/=.*/=***/'",
        timeout=30,
    )
    print("--- env ---")
    print(o3.read().decode())

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
