"""Wire /admin/dashboard API and restart backend."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vps_deploy_responsive as base  # noqa: E402

base.FILES = [
    "server.py",
    "core/admin_dashboard.py",
]

SYNC_CMDS = [
    "pm2 restart telegram-backend",
    "sleep 3 && curl -sf -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8000/admin/dashboard?window_hours=24'",
]

if __name__ == "__main__":
    code = base.main()
    if code != 0:
        raise SystemExit(code)
    if not os.environ.get("VPS_PASSWORD"):
        print("VPS_PASSWORD not set — uploaded only")
        raise SystemExit(0)
    import paramiko

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", username="root", password=os.environ["VPS_PASSWORD"], timeout=30)
    for cmd in SYNC_CMDS:
        print(f"\n>>> {cmd}")
        _, o, _ = c.exec_command(cmd, timeout=120)
        print(o.read().decode(errors="replace").strip())
        if o.channel.recv_exit_status() != 0:
            c.close()
            raise SystemExit(1)
    c.close()
    print("\nAdmin route deploy OK")
