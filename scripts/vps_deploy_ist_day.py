#!/usr/bin/env python3
"""Deploy IST calendar-day stats + dashboard bundle to VPS."""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
ROOT = Path(__file__).resolve().parent.parent
TF = Path(r"C:\Users\codet\TelegramForward")

BACKEND_FILES = [
    "core/ist_time.py",
    "core/stats_reset.py",
    "core/daily_stats.py",
    "core/join_cycle.py",
    "core/group_send_stats.py",
    "core/send_stats.py",
    "server.py",
]


def connect() -> paramiko.SSHClient:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, sock=sock)
    return c


def ensure_remote_dir(c: paramiko.SSHClient, remote_dir: str) -> None:
    c.exec_command(f"mkdir -p {remote_dir}")


def put_file(c: paramiko.SSHClient, sftp: paramiko.SFTPClient, local: Path, remote: str) -> None:
    ensure_remote_dir(c, remote.rsplit("/", 1)[0])
    sftp.put(str(local), remote)


def verify_ist(c: paramiko.SSHClient) -> None:
    cmd = (
        f"cd {REMOTE} && source venv/bin/activate && python3 - <<'PY'\n"
        "from core.ist_time import ist_date_str, ist_day_start_ts\n"
        "from core.stats_reset import get_effective_cutoff, stats_window_kind\n"
        "import time\n"
        "print('ist_date', ist_date_str())\n"
        "print('window', stats_window_kind())\n"
        "print('cutoff_age_h', round((time.time()-get_effective_cutoff())/3600, 2))\n"
        "PY"
    )
    _, stdout, stderr = c.exec_command(cmd, timeout=60)
    print(stdout.read().decode())
    err = stderr.read().decode().strip()
    if err:
        print("stderr:", err)


def main() -> None:
    c = connect()
    sftp = c.open_sftp()

    print("\n=== Backend (IST day cycle) ===")
    for rel in BACKEND_FILES:
        local = TF / rel
        if not local.exists():
            print(f"SKIP missing {local}")
            continue
        remote = f"{REMOTE}/{rel}"
        put_file(c, sftp, local, remote)
        print(f"  {rel}")

    static = ROOT / "static"
    if (static / "index.html").exists():
        print("\n=== Static bundle ===")
        n = 0
        for item in static.rglob("*"):
            if item.is_file():
                rel = item.relative_to(static).as_posix()
                put_file(c, sftp, item, f"{REMOTE}/static/{rel}")
                n += 1
        print(f"  uploaded {n} files")
    else:
        print("\nWARN: no static/ build — run npm run build in dashboard first")

    sftp.close()

    print("\n=== Verify IST on VPS ===")
    verify_ist(c)

    print("\n=== Restart backend ===")
    _, stdout, stderr = c.exec_command("pm2 restart telegram-backend", timeout=90)
    print(stdout.read().decode())
    err = stderr.read().decode().strip()
    if err:
        print(err)

    _, stdout, _ = c.exec_command(
        f"grep -o 'index-[^\"]*\\.js' {REMOTE}/static/index.html 2>/dev/null; "
        "curl -s -o /dev/null -w 'health %{http_code}\\n' http://127.0.0.1:8000/health",
        timeout=30,
    )
    print(stdout.read().decode())

    c.close()
    print("\nDone. Hard-refresh https://teleautomation.online (Ctrl+Shift+R)")


if __name__ == "__main__":
    main()
