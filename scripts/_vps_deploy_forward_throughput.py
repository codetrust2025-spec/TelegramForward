"""Deploy forward throughput + failure diagnostics (backend only)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vps_deploy_responsive as base  # noqa: E402

base.REMOTE = "/opt/telegramforward.old"
base.FILES = [
    "features/interval_forward.py",
    "workers/account_state.py",
    "workers/account_worker.py",
    "workers/feature_runtime.py",
]
base.REMOTE_CMDS = ["pm2 restart telegram-backend"]

if __name__ == "__main__":
    raise SystemExit(base.main())
