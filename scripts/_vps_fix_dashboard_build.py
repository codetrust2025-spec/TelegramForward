"""Diagnose and fix VPS dashboard vite build pointing at .old tree."""
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
        f"readlink -f {REMOTE}/dashboard",
        f"ls -la {REMOTE}/dashboard/src/App.jsx {REMOTE}.old/dashboard/src/App.jsx 2>&1",
        f"test -f {REMOTE}/dashboard/src/components/ui/ResponsiveOptions.jsx && echo RESPONSIVE_OK || echo RESPONSIVE_MISSING",
        f"test -f {REMOTE}.old/dashboard/src/components/ui/ResponsiveOptions.jsx && echo OLD_RESPONSIVE_OK || echo OLD_RESPONSIVE_MISSING",
        f"head -5 {REMOTE}/dashboard/vite.config.js",
        f"pwd && cd {REMOTE}/dashboard && pwd && npm run build 2>&1 | tail -20",
    ]
    for cmd in cmds:
        print(f"\n$ {cmd}")
        _, o, e = ssh.exec_command(cmd, timeout=120)
        out = o.read().decode("utf-8", errors="replace")
        err = e.read().decode("utf-8", errors="replace")
        if out.strip():
            print(out)
        if err.strip():
            print(err, file=sys.stderr)

    ssh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
