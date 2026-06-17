#!/usr/bin/env python3
"""Upload rebuilt static/ to production VPS."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

from _deploy_common import enforce_git_first

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
PROJECT = Path(__file__).resolve().parent.parent
STATIC = PROJECT / "static"
REMOTE_ROOT = "/opt/telegramforward"


def connect() -> paramiko.SSHClient:
    if not PASSWORD:
        raise SystemExit("Set VPS_PASSWORD environment variable")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    return client


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 300) -> tuple[str, str, int]:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return out, err, code


def upload_static(client: paramiko.SSHClient) -> None:
    if not STATIC.is_dir() or not (STATIC / "index.html").is_file():
        raise SystemExit(f"Missing local static build: {STATIC}")

    sftp = client.open_sftp()
    stamp_cmd = (
        f"mkdir -p {REMOTE_ROOT}/backups && "
        f"if [ -d {REMOTE_ROOT}/static ]; then "
        f"cp -a {REMOTE_ROOT}/static {REMOTE_ROOT}/backups/static_pre_deploy_$(date +%Y%m%d_%H%M%S); "
        f"fi && mkdir -p {REMOTE_ROOT}/static/assets"
    )
    out, err, code = run(client, stamp_cmd)
    if code != 0:
        raise SystemExit(f"Remote prep failed ({code}):\n{out}\n{err}")

    for path in STATIC.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(STATIC).as_posix()
        remote = f"{REMOTE_ROOT}/static/{rel}"
        remote_dir = remote.rsplit("/", 1)[0]
        try:
            sftp.stat(remote_dir)
        except OSError:
            run(client, f"mkdir -p {remote_dir}")
        sftp.put(str(path), remote)
        print(f"  uploaded {rel}")

    sftp.close()


def main() -> None:
    enforce_git_first()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    client = connect()
    try:
        out, _, _ = run(client, f"readlink -f {REMOTE_ROOT} 2>/dev/null || echo {REMOTE_ROOT}")
        print(f"Deploy target: {out.strip()}")
        print("Uploading static/ ...")
        upload_static(client)
        print("Verifying ...")
        verify, err, code = run(
            client,
            f"grep -o 'index-[^\\\"]*\\.js' {REMOTE_ROOT}/static/index.html; "
            f"curl -s -o /dev/null -w 'GET / -> %{{http_code}}\\n' http://127.0.0.1:8000/; "
            f"curl -s -o /dev/null -w 'GET /health -> %{{http_code}}\\n' http://127.0.0.1:8000/health",
        )
        print(verify)
        if err.strip():
            print(err, file=sys.stderr)
        if code != 0:
            raise SystemExit(code)
        print("Done. Hard-refresh https://teleautomation.online (Ctrl+Shift+R)")
    finally:
        client.close()


if __name__ == "__main__":
    main()
