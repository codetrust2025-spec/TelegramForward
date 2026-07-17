#!/usr/bin/env python3
"""Deploy recruitment_mail_api.py fix to VPS and restart backend."""
from __future__ import annotations
import os, socket, sys
from pathlib import Path
import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REMOTE = "/opt/telegramforward"
ROOT = Path(__file__).resolve().parent.parent

FILES = [
    "core/recruitment_mail_api.py",
]

def connect() -> paramiko.SSHClient:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, sock=sock)
    return c

def main() -> None:
    if not PASSWORD:
        print("Set VPS_PASSWORD environment variable")
        sys.exit(1)

    c = connect()
    sftp = c.open_sftp()

    for rel in FILES:
        local = ROOT / rel
        remote = f"{REMOTE}/{rel}"
        sftp.put(str(local), remote)
        print(f"Uploaded {rel}")

    sftp.close()

    _, stdout, stderr = c.exec_command("pm2 restart telegram-backend", timeout=60)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print("STDERR:", err[:500])

    # Verify the fix is live
    _, stdout2, _ = c.exec_command(
        "grep -c 'DISTINCT candidate_id' /opt/telegramforward/core/recruitment_mail_api.py",
        timeout=10
    )
    count = stdout2.read().decode().strip()
    print(f"\nVerification — 'DISTINCT candidate_id' occurrences in deployed file: {count}")
    if count == "2":
        print("Fix confirmed live on VPS.")
    else:
        print("WARNING: unexpected count, check the file manually.")

    c.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
