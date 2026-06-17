#!/usr/bin/env python3
from __future__ import annotations

import socket
import sys

import paramiko

PASSWORD = "8897870998s@SS"
HOST = "187.127.169.159"


def main() -> None:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username="root", password=PASSWORD, sock=sock)
    cmd = (
        "grep -r get_last_post_timestamp /opt/telegramforward.old --include='*.py' 2>/dev/null; "
        "echo '---'; "
        "cd /opt/telegramforward.old && git show HEAD:core/send_stats.py 2>/dev/null | "
        "grep -A20 'def get_last_post_timestamp' || "
        "ls -la /opt/telegramforward.old/core/send_stats.py* 2>/dev/null"
    )
    _, stdout, stderr = c.exec_command(cmd, timeout=60)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print("ERR", err)
    c.close()


if __name__ == "__main__":
    main()
