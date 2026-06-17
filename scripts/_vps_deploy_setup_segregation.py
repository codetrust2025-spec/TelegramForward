"""Deploy Setup column campaign/forwarding segregation to production."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vps_deploy_responsive as base  # noqa: E402

base.FILES = list(base.FILES) + [
    "dashboard/src/components/AccountPanel.jsx",
    "dashboard/src/components/AccountCard.jsx",
    "dashboard/src/components/PostingModePanel.jsx",
    "dashboard/src/utils/accountUi.js",
    "dashboard/src/index.css",
]

if __name__ == "__main__":
    raise SystemExit(base.main())
