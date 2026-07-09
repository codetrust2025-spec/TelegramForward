#!/usr/bin/env python3
"""Deploy AI payment proof extraction feature to VPS.

Uploads:
  - features/ollama_payment_extract.py (new)
  - core/public_slot_api.py (modified)
  - server.py (modified)
  - static/ (rebuilt dashboard)
Then restarts the backend.
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import paramiko

from _deploy_common import enforce_git_first

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward.old"
ROOT = Path(__file__).resolve().parent.parent

BACKEND_FILES = [
    "features/ollama_payment_extract.py",
    "core/public_slot_api.py",
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
    print(f"  ✓ {local.name}")


def main() -> None:
    enforce_git_first()

    if not PASSWORD:
        print("❌ Set VPS_PASSWORD environment variable first")
        sys.exit(1)

    print("🚀 Deploying AI payment proof extraction to VPS")
    print(f"   Host: {HOST}")
    print(f"   Remote: {REMOTE}")

    c = connect()
    sftp = c.open_sftp()

    # ── Backend files ───────────────────────────────────────────────────────
    print("\n📦 Backend files:")
    for rel in BACKEND_FILES:
        local = ROOT / rel
        remote = f"{REMOTE}/{rel}"
        if not local.exists():
            print(f"  ⚠ SKIP missing: {rel}")
            continue
        put_file(c, sftp, local, remote)

    # ── Static bundle ───────────────────────────────────────────────────────
    static = ROOT / "static"
    if (static / "index.html").exists():
        print("\n📦 Dashboard static:")
        n = 0
        for item in static.rglob("*"):
            if item.is_file():
                rel = item.relative_to(static).as_posix()
                remote_path = f"{REMOTE}/static/{rel}"
                ensure_remote_dir(c, remote_path.rsplit("/", 1)[0])
                sftp.put(str(item), remote_path)
                n += 1
        print(f"  ✓ {n} files uploaded")
    else:
        print("\n⚠ No static/ build found — skipping dashboard")

    sftp.close()

    # ── Restart backend ─────────────────────────────────────────────────────
    print("\n🔄 Restarting backend...")
    _, stdout, _ = c.exec_command("pm2 restart telegram-backend", timeout=60)
    output = stdout.read().decode("utf-8", errors="replace")
    print(output)

    c.close()
    print("✅ Done! AI payment extraction is live.")
    print("\n📝 Remember: SSH tunnel must be running on your laptop for Ollama AI to work.")


if __name__ == "__main__":
    main()
