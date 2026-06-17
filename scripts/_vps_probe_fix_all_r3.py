"""Quick post-deploy probe."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"


def main() -> int:
    pwd = os.environ.get("VPS_PASSWORD", "")
    if not pwd:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=pwd, timeout=30)

    checks = [
        ("health", "curl -sf http://127.0.0.1:8000/health"),
        ("bundle", "grep -oE 'app-[A-Za-z0-9_-]+\\.js' /opt/telegramforward/static/index.html | head -1"),
        (
            "access",
            "cd /opt/telegramforward && PYTHONPATH=/opt/telegramforward "
            "/opt/telegramforward/venv/bin/python -c "
            "\"from core.dashboard_access import handler_forbidden_path; "
            "print('fleet_open', not handler_forbidden_path('/inbox','GET'))\"",
        ),
        (
            "wa_status_auth",
            "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/whatsapp/status",
        ),
        (
            "wa_webhook_secret",
            "grep -q '^WHATSAPP_WEBHOOK_SECRET=' /opt/telegramforward/.env && echo set || echo missing",
        ),
    ]
    for name, cmd in checks:
        _, o, e = c.exec_command(cmd, timeout=30)
        out = (o.read() + e.read()).decode("utf-8", errors="replace").strip()
        print(f"{name}: {out}")

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
