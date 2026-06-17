"""Check dashboard nav fix on VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> int:
    import paramiko

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username="root", password=PASSWORD, timeout=30)

    cmds = [
        f"grep -c WORKSPACE_FLEET {REMOTE}/dashboard/src/desktop/DesktopApp.jsx",
        f"grep -c 'fleet' {REMOTE}/dashboard/src/utils/workspaceMode.js",
        f"ls -t {REMOTE}/static/assets/*.js 2>/dev/null | head -1",
    ]
    for cmd in cmds:
        print(f"$ {cmd}")
        _, o, e = ssh.exec_command(cmd, timeout=30)
        print(o.read().decode().strip())
        err = e.read().decode().strip()
        if err:
            print(err)

    _, o, _ = ssh.exec_command(
        f"ls -t {REMOTE}/static/assets/*.js 2>/dev/null | head -1 | xargs grep -c \"fleet\" 2>/dev/null || echo 0",
        timeout=30,
    )
    print("bundle_fleet_mentions:", o.read().decode().strip())

    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
