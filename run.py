#!/usr/bin/env python3
"""
Default entrypoint — ALWAYS auto-reload unless you opt out.

  python run.py              → backend + frontend (auto-restart on save)
  python run.py --backend    → backend only (auto-restart on save)
  python run.py --no-reload  → backend without file watch
  python run.py --production → same as --no-reload (use PM2 ecosystem for watch)
  python run.py --keep-alive    → production on :8000, auto-restart if crash (Windows)

You never need to manually restart after editing code.
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    os.chdir(ROOT)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("RELOAD_DELAY", "1.0")

    args = sys.argv[1:]
    if "--keep-alive" in args:
        cmd = [sys.executable, os.path.join(ROOT, "scripts", "keep_alive.py")]
        return subprocess.call(cmd, cwd=ROOT, env=env)
    if "--no-reload" in args or "--production" in args:
        env["NO_RELOAD"] = "1"
        cmd = [sys.executable, os.path.join(ROOT, "scripts", "uvicorn_reload.py")]
    elif "--backend" in args:
        env.pop("NO_RELOAD", None)
        cmd = [sys.executable, os.path.join(ROOT, "scripts", "uvicorn_reload.py")]
    else:
        env.pop("NO_RELOAD", None)
        cmd = [sys.executable, os.path.join(ROOT, "scripts", "dev.py")]

    return subprocess.call(cmd, cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
