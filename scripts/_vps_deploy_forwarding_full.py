"""Deploy forwarding cap, join-every-2-ticks, and forwarding-only UI filter sync."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vps_deploy_responsive as base  # noqa: E402

base.FILES = [
    "core/posting_mode.py",
    "core/forward_message_batch.py",
    "features/interval_forward.py",
    "workers/account_worker.py",
    "workers/account_state.py",
    "dashboard/src/App.jsx",
    "dashboard/src/utils/accountUi.js",
    "dashboard/src/components/AccountPanel.jsx",
    "dashboard/src/components/AccountCard.jsx",
    "dashboard/src/components/PostingModePanel.jsx",
    "dashboard/src/components/DailyStatsPanel.jsx",
    "dashboard/src/components/ProgressHubPanel.jsx",
    "dashboard/src/index.css",
]

SYNC_CMDS = [
    "pm2 restart telegram-backend",
    "sleep 2 && curl -sf http://127.0.0.1:8000/health | head -c 200 || echo health_check_failed",
]

if __name__ == "__main__":
    code = base.main()
    if code != 0:
        raise SystemExit(code)
    if not os.environ.get("VPS_PASSWORD"):
        print("VPS_PASSWORD not set — files uploaded and dashboard built; backend restart skipped")
        raise SystemExit(0)
    import paramiko

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", username="root", password=os.environ["VPS_PASSWORD"], timeout=30)
    for cmd in SYNC_CMDS:
        print(f"\n>>> {cmd}")
        _, o, e = c.exec_command(cmd, timeout=120)
        out = o.read().decode(errors="replace")
        if out:
            print(out.strip())
        err = e.read().decode(errors="replace")
        if err.strip():
            print(err.strip(), file=sys.stderr)
        if o.channel.recv_exit_status() != 0:
            c.close()
            raise SystemExit(1)
    c.close()
    print("\nDeploy OK — hard refresh https://teleautomation.online")
    print("Restart forwarding workers (Stop → Start) on account6/7/8 if already running.")
