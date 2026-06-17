"""Deploy Fleet today reach split (campaign vs forwarding)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _vps_deploy_responsive import FILES, HOST, REMOTE, REMOTE_CMDS, USER  # noqa: E402

EXTRA = [
    "workers/account_worker.py",
]

FILES = list(FILES) + EXTRA


def main() -> int:
    import _vps_deploy_responsive as mod

    mod.FILES = FILES
    return mod.main()


if __name__ == "__main__":
    raise SystemExit(main())
