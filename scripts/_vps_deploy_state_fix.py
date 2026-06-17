"""Hotfix: /state 500 from lifecycle reading removed AccountState.status fields."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vps_deploy_responsive as base  # noqa: E402

base.FILES = [
    "services/account_manager.py",
    "workers/account_state.py",
    "workers/account_worker.py",
]

SYNC_CMDS = [
    "pm2 restart telegram-backend",
    "sleep 3 && curl -sf http://127.0.0.1:8000/state | head -c 120 || echo state_failed",
    "curl -sf http://127.0.0.1:8000/health | head -c 80",
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
        _, o, e = c.exec_command(cmd, timeout=120)
        out = o.read().decode(errors="replace").strip()
        print(out or "(empty)")
        if o.channel.recv_exit_status() != 0 and "state_failed" not in out:
            print(e.read().decode(errors="replace")[:500])
            c.close()
            raise SystemExit(1)
    c.close()
    print("\nState fix deploy OK")
