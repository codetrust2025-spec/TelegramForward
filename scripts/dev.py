#!/usr/bin/env python3
"""
Development launcher — backend auto-reload + frontend HMR.

Save any .py file → backend restarts automatically (no manual restart).
Running workers are persisted and resume after reload.

Usage:
  python scripts/dev.py
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

from core.auto_reload import RestartRateGuard, reload_delay_seconds
DASHBOARD = os.path.join(ROOT, "dashboard")
UVICORN_RELOAD = os.path.join(ROOT, "scripts", "uvicorn_reload.py")

BACKEND_RESPAWN_DELAY = max(2.0, reload_delay_seconds())


def _spawn_backend(env: dict) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, UVICORN_RELOAD],
        cwd=ROOT,
        env=env,
    )


def main() -> int:
    print("=" * 60)
    print("TelegramForward - AUTO-RELOAD DEV MODE")
    print("  Backend : http://127.0.0.1:8000  (reload on .py / .env save)")
    print("  Frontend: http://127.0.0.1:3000  (Vite HMR)")
    print("  Save code -> system restarts automatically - NO manual restart")
    print("  Running workers resume after reload (data/.running_workers.json)")
    print("  Log: data/reload.log")
    print("=" * 60)

    try:
        from core.system_lifecycle import log_system_event

        log_system_event("Dev launcher started", reason="cold_start", detail="file watch + Vite HMR")
    except Exception:
        pass

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("RELOAD_DELAY", str(reload_delay_seconds()))
    env.pop("NO_RELOAD", None)

    backend = _spawn_backend(env)
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=DASHBOARD,
        env=env,
        shell=sys.platform == "win32",
    )

    respawn_guard = RestartRateGuard()

    def shutdown(*_args):
        print("\n[dev] Shutting down...")
        for proc in (frontend, backend):
            if proc.poll() is None:
                proc.terminate()
        time.sleep(0.5)
        for proc in (frontend, backend):
            if proc.poll() is None:
                proc.kill()
        sys.exit(0)

    def maybe_respawn_backend(exit_code: int):
        nonlocal backend
        if not respawn_guard.allow():
            print("[dev] Backend respawn limit reached — not restarting (crash loop?)")
            shutdown()
        print(f"[dev] Backend exited — auto-respawning in {BACKEND_RESPAWN_DELAY}s...")
        respawn_guard.wait_before_restart()
        try:
            from core.system_lifecycle import log_system_event

            log_system_event(
                "Dev launcher respawning backend",
                reason="crash",
                detail=f"exit code {exit_code}",
            )
        except Exception:
            pass
        backend = _spawn_backend(env)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            bc = backend.poll()
            fc = frontend.poll()
            if bc is not None:
                print(f"[dev] Backend process ended (code {bc})")
                maybe_respawn_backend(bc)
                continue
            if fc is not None:
                print(f"[dev] Frontend exited ({fc})")
                shutdown()
            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
