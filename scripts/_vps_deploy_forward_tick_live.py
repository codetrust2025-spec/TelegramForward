"""Deploy live forward-tick progress (backend + dashboard)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vps_deploy_responsive as base  # noqa: E402

base.FILES = list(base.FILES) + [
    "core/forward_message_batch.py",
    "core/posting_mode.py",
    "features/interval_forward.py",
    "workers/account_worker.py",
    "services/forward_message_service.py",
    "services/account_manager.py",
    "server.py",
    "dashboard/src/components/AccountCard.jsx",
    "dashboard/src/components/PostingModePanel.jsx",
    "dashboard/src/components/ForwardMessagePanel.jsx",
    "dashboard/src/App.jsx",
    "dashboard/src/index.css",
]

SYNC_CMDS = [
    "pm2 restart telegram-backend",
    "sleep 2 && curl -sf http://127.0.0.1:8000/health | head -c 120 || echo health_check_failed",
]

if __name__ == "__main__":
    code = base.main()
    if code != 0:
        raise SystemExit(code)
    if not os.environ.get("VPS_PASSWORD"):
        raise SystemExit(1)
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
    print("\nLive forward tick deploy OK — restart Kalyan worker if already running")
