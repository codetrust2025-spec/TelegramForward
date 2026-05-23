#!/usr/bin/env python3
"""
Keep TelegramForward running on Windows (and other OS).

- Serves UI + API on http://127.0.0.1:8000 (one address, no separate :3000)
- Restarts the backend automatically if it crashes or exits
- Run via: python scripts/keep_alive.py  or double-click START.bat
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_INDEX = os.path.join(ROOT, "static", "index.html")
DASHBOARD_DIR = os.path.join(ROOT, "dashboard")
UVICORN = os.path.join(ROOT, "scripts", "uvicorn_reload.py")
HEALTH_URL = "http://127.0.0.1:8000/health"
OPEN_URL = "http://127.0.0.1:8000/"


def _log(msg: str) -> None:
    print(msg, flush=True)


def _health_ok() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=3) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _ensure_dashboard_built() -> None:
    if os.path.isfile(STATIC_INDEX):
        return
    _log("[keep-alive] Building dashboard (first run only)...")
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    subprocess.run(
        [npm, "run", "build"],
        cwd=DASHBOARD_DIR,
        shell=sys.platform == "win32",
        check=False,
    )
    if not os.path.isfile(STATIC_INDEX):
        _log("[keep-alive] WARN: static/index.html missing — run: cd dashboard && npm run build")


def _port_in_use(port: int = 8000) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _spawn_backend() -> subprocess.Popen | None:
    if _health_ok():
        _log("[keep-alive] Backend already healthy on :8000 — not starting a duplicate.")
        return None
    if _port_in_use(8000):
        _log("[keep-alive] Port 8000 busy but health check failed — wait or close other servers.")
        time.sleep(5.0)
        if _health_ok():
            return None
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["NO_RELOAD"] = "1"
    env.setdefault("HOST", "127.0.0.1")
    env.setdefault("PORT", "8000")
    return subprocess.Popen(
        [sys.executable, UVICORN],
        cwd=ROOT,
        env=env,
    )


def _open_browser_once() -> None:
    if getattr(_open_browser_once, "_done", False):
        return
    try:
        if sys.platform == "win32":
            os.startfile(OPEN_URL)  # type: ignore[attr-defined]
        else:
            import webbrowser

            webbrowser.open(OPEN_URL)
        _open_browser_once._done = True  # type: ignore[attr-defined]
    except OSError:
        pass


def main() -> int:
    os.chdir(ROOT)
    _ensure_dashboard_built()

    _log("=" * 60)
    _log("TelegramForward — KEEP ALIVE MODE")
    _log("  Open:  http://127.0.0.1:8000")
    _log("  Do not close this window while using the app.")
    _log("  If it crashes, this script restarts it automatically.")
    _log("=" * 60)

    delay = 3.0
    browser_opened = False

    while True:
        _log("[keep-alive] Starting backend...")
        proc = _spawn_backend()

        for _ in range(60):
            if proc is None:
                break
            if proc.poll() is not None:
                break
            if _health_ok():
                if not browser_opened:
                    _open_browser_once()
                    browser_opened = True
                break
            time.sleep(0.5)

        if proc is None:
            time.sleep(5.0)
            continue
        code = proc.wait()
        _log(f"[keep-alive] Backend stopped (exit {code}). Restarting in {delay:.0f}s...")
        time.sleep(delay)
        delay = min(30.0, delay + 2.0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        _log("\n[keep-alive] Stopped by user.")
        raise SystemExit(0)
