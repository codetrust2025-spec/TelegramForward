"""List dashboard operator logins + Telegram account sessions on VPS (no passwords)."""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> int:
    if not PASSWORD:
        print("Set VPS_PASSWORD to query production.", file=sys.stderr)
        return 1

    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    import paramiko as _  # noqa: F401

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_script = os.path.join(repo, "scripts", "_vps_list_logins_remote.py")
    remote_script = f"{REMOTE}/scripts/_vps_list_logins_remote.py"
    sftp = client.open_sftp()
    sftp.put(local_script, remote_script)
    sftp.close()
    _, stdout, stderr = client.exec_command(
        f"cd {REMOTE} && python3 {remote_script}",
        timeout=60,
    )
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    client.close()
    if err.strip():
        print(err, file=sys.stderr)
    print(out)
    return 0 if out.strip() else 1


if __name__ == "__main__":
    raise SystemExit(main())
