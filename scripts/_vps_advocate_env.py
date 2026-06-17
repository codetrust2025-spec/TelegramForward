"""Upload Advocate OS .env from local Desktop and restart backend."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER = "187.127.169.159", "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
LOCAL_ENV = os.path.join(
    os.environ.get("USERPROFILE", ""),
    "Desktop",
    "legal-casebot-backend",
    ".env",
)
REMOTE_ENV = "/var/www/advocate-os/legal-casebot-backend/.env"


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1
    if not os.path.isfile(LOCAL_ENV):
        print(f"Missing {LOCAL_ENV}", file=sys.stderr)
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()
    sftp.put(LOCAL_ENV, REMOTE_ENV)
    sftp.close()

    patch = (
        f"sed -i 's|^CLIENT_URL=.*|CLIENT_URL=https://advocateos.in,http://187.127.169.159|' {REMOTE_ENV}; "
        "grep -q '^NODE_ENV=' /var/www/advocate-os/legal-casebot-backend/.env || "
        "echo 'NODE_ENV=production' >> /var/www/advocate-os/legal-casebot-backend/.env; "
        "pm2 restart advocate-backend; sleep 3; "
        "curl -sf -m 10 http://127.0.0.1:5000/health && echo HEALTH_OK || pm2 logs advocate-backend --lines 8 --nostream"
    )
    print(">>> patch env + restart")
    _stdin, stdout, stderr = client.exec_command(patch, get_pty=True, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace")
    if out:
        print(out)
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
