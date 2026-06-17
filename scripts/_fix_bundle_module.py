"""Fix blank page: load Vite bundle as ES module + paired CSS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER = "187.127.169.159", "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_INDEX = os.path.join(REPO, "static", "index.html")
REMOTE_INDEX = "/opt/telegramforward/static/index.html"
REMOTE_JS = "/opt/telegramforward/static/assets/dashboard.bundle.js"
SOURCE_JS = "/opt/telegramforward/static/assets/index-buYID2R_.js"


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    # Regenerate index.html with type=module
    import subprocess

    subprocess.run([sys.executable, os.path.join(REPO, "scripts", "_write_bundle_index.py")], check=True)

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    # Ensure dashboard.bundle.js is the full Vite entry (not trimmed copy)
    c.exec_command(f"cp {SOURCE_JS} {REMOTE_JS}")
    _, o, _ = c.exec_command(f"stat -c %s {REMOTE_JS}")
    print(f"dashboard.bundle.js size: {o.read().decode().strip()}")

    sftp = c.open_sftp()
    sftp.put(LOCAL_INDEX, REMOTE_INDEX)
    sftp.close()
    c.close()
    print("Deployed index.html with type=module")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
