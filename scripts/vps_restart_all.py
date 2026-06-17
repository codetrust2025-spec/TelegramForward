#!/usr/bin/env python3
"""Restart all TeleAutomation server processes on VPS."""
from __future__ import annotations

import socket
import sys

import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = "REMOVED_VPS_PASSWORD"


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 180) -> tuple[str, str, int]:
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return out, err, code


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sock = socket.create_connection((HOST, 22), timeout=30)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=HOST, username=USER, password=PASSWORD, sock=sock)

    script = r"""
set -e
echo "=== PM2 processes (before) ==="
pm2 list || true

echo ""
echo "=== Restarting PM2 (all apps, reload env) ==="
cd /opt/telegramforward.old 2>/dev/null || cd /opt/telegramforward
set -a && . ./.env && set +a
pm2 restart all --update-env 2>&1

echo ""
echo "=== PM2 save ==="
pm2 save 2>&1 || true

echo ""
echo "=== Nginx ==="
if command -v nginx >/dev/null 2>&1; then
  nginx -t 2>&1 && systemctl reload nginx 2>&1 || systemctl restart nginx 2>&1
  systemctl is-active nginx 2>&1 || true
else
  echo "nginx not installed"
fi

echo ""
echo "=== Wait for backend ==="
sleep 5

echo ""
echo "=== Health check ==="
curl -sf http://127.0.0.1:8000/health && echo " backend OK" || echo " backend health FAILED"

echo ""
echo "=== PM2 processes (after) ==="
pm2 list

echo ""
echo "=== Recent PM2 logs (last 15 lines) ==="
pm2 logs telegram-backend --lines 15 --nostream 2>&1 || true
"""
    out, err, code = run(client, script, timeout=180)
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    client.close()
    if code != 0:
        raise SystemExit(code)
    print("\nDone — all server processes restarted.")


if __name__ == "__main__":
    main()
