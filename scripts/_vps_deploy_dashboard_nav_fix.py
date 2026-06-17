"""Deploy desktop Dashboard sidebar nav fix (fleet workspace mode)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = [
    "dashboard/src/utils/workspaceMode.js",
    "dashboard/src/utils/workspaceDashboard.js",
    "dashboard/src/desktop/DesktopApp.jsx",
]

REMOTE_CMDS = [
    f"cd {REMOTE}/dashboard && npm run build 2>&1",
    f"ls -t {REMOTE}/static/assets/app-*.js 2>/dev/null | head -2",
    f"grep -l WORKSPACE_FLEET {REMOTE}/dashboard/src/desktop/DesktopApp.jsx",
]


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

    for rel in FILES:
        local = os.path.join(repo, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        print(f"  upload {rel}")
        sftp.put(local, remote)

    sftp.close()

    for cmd in REMOTE_CMDS:
        print(f"$ {cmd}")
        _in, stdout, stderr = client.exec_command(cmd, timeout=300)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out.strip():
            print(out.strip())
        if err.strip():
            print(err.strip(), file=sys.stderr)

    client.close()
    print("deploy ok: 2026-06-05-dashboard-nav-fleet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
