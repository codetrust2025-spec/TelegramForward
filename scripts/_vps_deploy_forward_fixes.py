"""Deploy forwarding audit fixes (FW-001 through FW-010)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _vps_deploy_responsive as base  # noqa: E402

base.FILES = [
    "core/telegram_forward.py",
    "core/joined_membership.py",
    "features/telegram_joined_stats.py",
    "features/interval_forward.py",
    "services/forward_message_service.py",
    "server.py",
    "dashboard/src/components/ForwardMessagePanel.jsx",
    "docs/FORWARD_MESSAGE_BATCH.md",
]

base.REMOTE_CMDS = [
    f"cd {base.REMOTE}/dashboard && npm run build",
    "pm2 restart telegram-backend",
]

if __name__ == "__main__":
    raise SystemExit(base.main())
