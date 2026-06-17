"""Restore full dashboard.bundle.js from VPS backup if truncated."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE_STATIC = "187.127.169.159", "root", "/opt/telegramforward/static"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_STATIC = os.path.join(REPO, "static")
REMOTE_JS = f"{REMOTE_STATIC}/assets/dashboard.bundle.js"
REMOTE_CSS = f"{REMOTE_STATIC}/assets/dashboard.bundle.css"
LOCAL_JS = os.path.join(LOCAL_STATIC, "assets", "dashboard.bundle.js")
LOCAL_CSS = os.path.join(LOCAL_STATIC, "assets", "dashboard.bundle.css")

# Full bundle is ~3.4MB; stripped Vite copy is ~1MB
MIN_FULL_SIZE = 2_500_000


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    # Find largest dashboard.bundle.js on VPS (full backup among static assets)
    _, o, _ = c.exec_command(
        "ls -la /opt/telegramforward/static/assets/dashboard.bundle.js "
        "/opt/telegramforward/static/assets/dashboard.bundle.js.bak* 2>/dev/null; "
        "find /opt/telegramforward/static/assets -name 'dashboard.bundle.js*' -size +2500k 2>/dev/null"
    )
    print(o.read().decode("utf-8", "replace"))

    _, o, _ = c.exec_command(f"stat -c %s {REMOTE_JS} 2>/dev/null || echo 0")
    size = int((o.read().decode().strip() or "0"))
    print(f"Current remote bundle size: {size}")

    if size >= MIN_FULL_SIZE:
        print("Remote bundle already full size — checking Daily ops...")
    else:
        # Try backup paths
        candidates = [
            "/opt/telegramforward/static/assets/dashboard.bundle.js.full",
            "/opt/telegramforward/static/assets/dashboard.bundle.js.orig",
        ]
        _, o, _ = c.exec_command(
            "find /opt/telegramforward/static/assets -name '*.js' -size +3000k 2>/dev/null | head -5"
        )
        large = [ln.strip() for ln in o.read().decode().splitlines() if ln.strip()]
        print("Large JS candidates:", large)

        source = None
        for path in candidates + large:
            _, o, _ = c.exec_command(
                f"grep -q 'Daily ops' {path} 2>/dev/null && echo yes || echo no"
            )
            if o.read().decode().strip() == "yes":
                source = path
                break

        if not source:
            # Re-fetch from teleautomation-app build on VPS dashboard src - use index-buYID2R_.js
            for path in [
                "/opt/telegramforward/static/assets/index-buYID2R_.js",
                "/opt/telegramforward/static/assets/index-DSit0S3F.js",
                "/opt/telegramforward/static/assets/index-5Fb00iKl.js",
            ]:
                _, o, _ = c.exec_command(
                    f"grep -q 'Daily ops' {path} 2>/dev/null && stat -c %s {path} || echo 0"
                )
                out = o.read().decode().strip().split()
                if out and out[0] != "0":
                    source = path
                    print(f"Using source: {path} ({out[0]} bytes)")
                    break

        if source and source != REMOTE_JS:
            c.exec_command(f"cp {REMOTE_JS} {REMOTE_JS}.trimmed.bak")
            c.exec_command(f"cp {source} {REMOTE_JS}")
            print(f"Restored {REMOTE_JS} from {source}")

    sftp = c.open_sftp()
    try:
        sftp.get(REMOTE_JS, LOCAL_JS)
        sftp.get(REMOTE_CSS, LOCAL_CSS)
    finally:
        sftp.close()

    with open(LOCAL_JS, "rb") as f:
        data = f.read()
    t = data.decode("utf-8", "replace")
    print(f"Local bundle size: {len(data)}")
    for label in ["Daily ops", "Works pending", "daily-ops", "cand-workspace", "Pending only"]:
        print(f"  {label}: {t.count(label)}")

    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
