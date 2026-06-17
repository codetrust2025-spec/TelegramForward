"""Deploy real sw.js (nginx was serving index.html for /sw.js)."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()
    local = os.path.join(REPO, "static", "sw.js")
    remote = f"{REMOTE}/static/sw.js"
    sftp.put(local, remote)
    sftp.close()
    print("uploaded static/sw.js")

    cmds = [
        f"grep -n 'sw.js' /etc/nginx/sites-enabled/* 2>/dev/null | head -20 || true",
        "curl -sI https://teleautomation.online/sw.js | head -6",
        "curl -s https://teleautomation.online/sw.js | head -3",
    ]
    for cmd in cmds:
        print(">>>", cmd)
        _, o, e = c.exec_command(cmd, timeout=30)
        print(o.read().decode("utf-8", errors="replace"))
        err = e.read().decode()
        if err.strip():
            print(err[:200])

    c.close()
    print("Done — users should: DevTools → Application → Unregister service worker → hard refresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
