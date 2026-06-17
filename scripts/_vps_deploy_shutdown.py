"""Deploy auto-shutdown list: 6h no posts → 7-day rest (campaign + forwarding)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vps_deploy_responsive as base  # noqa: E402

base.FILES = [
    "core/account_shutdown.py",
    "core/account_shutdown_monitor.py",
    "core/group_send_stats.py",
    "core/send_stats.py",
    "services/account_manager.py",
    "server.py",
    "workers/account_state.py",
    "workers/account_worker.py",
    "features/interval_forward.py",
    "dashboard/src/index.css",
    "dashboard/src/utils/accountUi.js",
    "dashboard/src/utils/globalStats.js",
    "dashboard/src/components/ShutdownListPanel.jsx",
    "dashboard/src/components/AccountPanel.jsx",
    "dashboard/src/components/AccountCard.jsx",
    "dashboard/src/components/ProgressHubPanel.jsx",
    "dashboard/src/App.jsx",
]

SYNC_CMDS = [
    "pm2 restart telegram-backend",
    "sleep 2 && curl -sf http://127.0.0.1:8000/health | head -c 80",
]

if __name__ == "__main__":
    code = base.main()
    if code != 0:
        raise SystemExit(code)
    if not os.environ.get("VPS_PASSWORD"):
        print("VPS_PASSWORD not set — uploaded + built only")
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
    print("\nShutdown list deploy OK")
