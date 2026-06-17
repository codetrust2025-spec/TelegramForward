"""Deploy forward stats clarity (tick vs since-reset labels + mode-aware fleet aggregation)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vps_deploy_responsive as base  # noqa: E402

base.REMOTE = "/opt/telegramforward.old"
base.FILES = [
    "workers/account_state.py",
    "dashboard/src/App.jsx",
    "dashboard/src/utils/globalStats.js",
    "dashboard/src/utils/accountUi.js",
    "dashboard/src/utils/fleetReachHelp.js",
    "dashboard/src/components/DailyStatsPanel.jsx",
    "dashboard/src/components/ProgressHubPanel.jsx",
    "dashboard/src/components/ProgressStatsPanel.jsx",
]

base.REMOTE_CMDS = [
    f"cd {base.REMOTE}/dashboard && npm run build",
    "pm2 restart telegram-backend",
]

if __name__ == "__main__":
    raise SystemExit(base.main())
