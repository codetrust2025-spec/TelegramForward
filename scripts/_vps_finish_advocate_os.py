"""Finish Advocate OS VPS setup after _deploy_prod.py upload."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, APP = "187.127.169.159", "root", "/var/www/advocate-os"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

CMDS = [
    f"mkdir -p {APP}",
    f"sed -i 's/\\r$//' {APP}/legal-casebot-backend/scripts/deploy-vps.sh",
    f"APP_DIR={APP} bash {APP}/legal-casebot-backend/scripts/deploy-vps.sh",
    "pm2 describe advocate-backend 2>/dev/null | head -6 || echo NO_PM2",
    "curl -sf -m 10 http://127.0.0.1:5000/health || echo HEALTH_FAIL",
    f"grep -l 'dash-home--figma' {APP}/legal-casebot/build/static/js/*.js 2>/dev/null | head -1 || echo BUILD_GREP_FAIL",
    "grep -r advocateos /etc/nginx/sites-enabled/ /etc/nginx/conf.d/ 2>/dev/null | head -5 || echo NO_NGINX",
]


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    for cmd in CMDS:
        print(f"\n>>> {cmd}")
        _stdin, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=900)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out:
            print(out[-12000:])
        if err.strip():
            print(err[-4000:], file=sys.stderr)
        if stdout.channel.recv_exit_status() != 0 and "||" not in cmd:
            client.close()
            return 1

    client.close()
    print("\nAdvocate OS setup finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
