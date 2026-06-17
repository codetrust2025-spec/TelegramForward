#!/usr/bin/env python3
"""One-time: turn /opt/telegramforward into a git checkout (keeps data/ and .env)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from scripts.prod_sync_common import GITHUB_REPO, REMOTE, ssh_connect, ssh_run, vps_has_git  # noqa: E402

SETUP_SCRIPT = r"""
set -euo pipefail
export GIT_TERMINAL_PROMPT=0
cd __REMOTE__
REAL=$(readlink -f .)
cd "$REAL"

if [ -d .git ]; then
  echo "Git repo at $REAL"
  git remote set-url origin __REPO__ 2>/dev/null || git remote add origin __REPO__
else
  echo "Initializing git at $REAL (data/ and .env preserved)..."
  git init
  git remote add origin __REPO__
fi

git fetch --depth 1 origin main
git checkout -B main FETCH_HEAD
echo "Checked out main at $(git rev-parse --short HEAD)"
"""


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    password = os.environ.get("VPS_PASSWORD", "")
    if not password:
        print("Set VPS_PASSWORD", file=sys.stderr)
        return 1

    client = ssh_connect(password)
    try:
        if vps_has_git(client):
            print("VPS already has .git — syncing to origin/main...")
        else:
            print("VPS has no .git — initializing from GitHub...")

        script = (
            SETUP_SCRIPT.replace("__REMOTE__", REMOTE)
            .replace("__REPO__", GITHUB_REPO)
        )
        # Upload and run via bash -s
        cmd = f"bash -s <<'EOS'\n{script}\nEOS"
        code, out, err = ssh_run(client, cmd, timeout=180)
        print(out)
        if err.strip():
            print(err, file=sys.stderr)
        if code != 0:
            return code

        code, out, _ = ssh_run(client, f"cd {REMOTE} && git rev-parse HEAD && git status --short | head -5")
        print("VPS state:")
        print(out)
        print("\nDone. Use: python scripts/deploy_prod.py")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
