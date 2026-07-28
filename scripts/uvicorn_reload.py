#!/usr/bin/env python3
"""
Uvicorn with full-project auto-reload (watchfiles).

NON-NEGOTIABLE DEV BEHAVIOR:
  Save any .py / .env / server.py → automatic restart → no manual action.

Usage:
  python run.py
  python run.py --backend
  python scripts/uvicorn_reload.py

Environment:
  HOST, PORT, RELOAD_DELAY (debounce, default 1.0s)
  NO_RELOAD=1  — disable watch (use with PM2 file watch instead)
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

# PM2 can retain stale environment values across restarts. These settings
# control which inference host receives production AI traffic, so the checked
# application .env is authoritative for them.
try:
    from dotenv import dotenv_values

    _runtime_env = dotenv_values(os.path.join(ROOT, ".env"))
    for _name in (
        "OLLAMA_BASE_URL",
        "OLLAMA_REMOTE_ENABLED",
        "OLLAMA_EXPECT_REVERSE_SSH_TUNNEL",
        "OLLAMA_INFERENCE_HOST_ID",
    ):
        if _runtime_env.get(_name):
            os.environ[_name] = str(_runtime_env[_name])
except Exception:
    pass

from core.auto_reload import (
    RELOAD_DIRS,
    RELOAD_EXCLUDES,
    RELOAD_INCLUDES,
    ensure_cwd,
    reload_delay_seconds,
    reload_enabled,
)


def _banner() -> None:
    if not reload_enabled():
        print("TelegramForward backend — NO_RELOAD=1 (file watch off)")
        return
    print("=" * 60)
    print("AUTO-RELOAD ON - save code -> server restarts automatically")
    print("  No manual restart required")
    print(f"  Reload delay: {reload_delay_seconds()}s (anti loop)")
    print("  Watched: core/, features/, workers/, services/, scripts/, server.py")
    print("  Workers auto-resume: data/.running_workers.json")
    print("  Log: data/reload.log")
    print("=" * 60)
    try:
        from core.worker_persistence import log_reload_event

        log_reload_event("Watcher started — edit .py/.env to trigger auto-restart")
    except Exception:
        pass


def main() -> None:
    ensure_cwd()
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    use_reload = reload_enabled()
    delay = reload_delay_seconds()

    _banner()

    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=use_reload,
        reload_delay=delay,
        reload_dirs=RELOAD_DIRS if use_reload else None,
        reload_excludes=RELOAD_EXCLUDES if use_reload else None,
        reload_includes=RELOAD_INCLUDES if use_reload else None,
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
