"""Deploy account tab alignment CSS fixes."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vps_deploy_responsive as base  # noqa: E402

base.FILES = [
    "dashboard/src/index.css",
    "dashboard/src/App.jsx",
    "dashboard/src/components/AccountPanel.jsx",
    "dashboard/src/components/AccountCard.jsx",
    "dashboard/src/components/ui/MetricBlock.jsx",
    "dashboard/src/components/DailyStatsPanel.jsx",
]

if __name__ == "__main__":
    raise SystemExit(base.main())
