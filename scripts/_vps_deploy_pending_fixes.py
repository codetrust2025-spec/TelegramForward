"""Deploy Karthik inbox sweep fix + desktop Dashboard nav fix to VPS."""
from __future__ import annotations

import subprocess
import sys

SCRIPTS = [
    "_vps_deploy_karthik_bg_fix.py",
    "_vps_deploy_dashboard_nav_fix.py",
]


def main() -> int:
    root = __file__.replace("\\", "/").rsplit("/", 1)[0]
    for name in SCRIPTS:
        path = f"{root}/{name}"
        print(f"\n=== {name} ===")
        rc = subprocess.call([sys.executable, path])
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
