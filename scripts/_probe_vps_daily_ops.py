"""Probe VPS for interview routes and monolith bundle."""
from __future__ import annotations

import os
import sys

import paramiko

HOST = "187.127.169.159"
PWD = os.environ.get("VPS_PASSWORD", "")


def main() -> int:
    if not PWD:
        print("VPS_PASSWORD required", file=sys.stderr)
        return 1
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PWD, timeout=30)
    cmds = [
        "grep -n interviews /opt/telegramforward/server.py | head -50",
        "grep -c interview_global /opt/telegramforward/features/candidate_store.py",
        "stat -c '%n %s' /opt/telegramforward/static/assets/index-buYID2R_.js 2>&1",
        "stat -c '%n %s' /opt/telegramforward/static/assets/dashboard.bundle.js 2>&1",
    ]
    for cmd in cmds:
        print("===", cmd, "===")
        _, o, _ = c.exec_command(cmd)
        print(o.read().decode("utf-8", errors="replace"))
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
